from audio_manager import audio_system
from telemetry_logger import telemetry  # <-- Telemetri importerad
import depthai as dai
import blobconverter
import time
import threading
import cv2
import sys
import select
import uuid
import os
from collections import Counter  # <-- För att räkna filterbeslut

# Importera din fristående AI-modul enligt modularitetsprincipen
from gemini_service import GeminiService

class DetectionFilter:
    """
    ANSVAR: Hanterar filtrering av oviktiga objekt (Blacklist) samt beräknar
    om ett högprioriterat objekt kräver omedelbar akut-varning eller följer vanlig cooldown.
    Hanterar spårning individuellt per objekttyp för att undvika dataläckage mellan klasser.
    Äger även den digitala blindkäppens logik för dämpning av trappvarningar.
    """
    def __init__(self, cooldown_seconds=5.0, distance_threshold_meters=0.5, emergency_distance_meters=3.0,
                 emergency_repeat_seconds=4.0, emergency_closer_meters=0.3):
        self.cooldown = cooldown_seconds
        self.dist_threshold = distance_threshold_meters
        self.emergency_distance = emergency_distance_meters
        # Ett akut objekt som står still upprepas bara efter så här lång tid,
        # eller tidigare om det kommit så här mycket närmare.
        self.emergency_repeat = emergency_repeat_seconds
        self.emergency_closer = emergency_closer_meters
        
        # OOD-Struktur: Tillstånd spåras unikt per etikett (label) via ordböcker
        self.last_spoken_timestamps = {}
        self.last_distances = {}
        self.last_seen_timestamps = {}

        # Särskilda tillståndsvariabler för den digitala blindkäppen (Trapplogik)
        self.last_stair_warning_time = 0
        self.consecutive_stair_drops = 0
        self.last_ground_z = 0.0

        # Global takthållare för att ge Piper andningspauser mellan allmänna miljöbeskrivningar
        self.global_last_spoken_time = 0

        # Sortera bort spökdetektioner och orelevanta inomhusobjekt utomhus
        self.blacklist = {"flygplan", "paraply", "frisbee", "drake", "slips", "sportboll", "handväska"}
        
        # Högprioriterade trafikobjekt (Liv och död vid utomhusnavigering + person i närheten)
        self.high_priority = {"person", "bil", "buss", "lastbil", "motorcykel", "cykel", "trafikljus", "stoppskylt"}

        # TELEMETRI: Spårar varför saker blockeras
        self.rejection_counts = Counter()
        self.last_summary_time = time.time()

    def is_emergency_candidate(self, label, distance):
        """Är objektet ett akut hot (högprioriterad klass inom akutavstånd)?"""
        if label in self.blacklist or label not in self.high_priority:
            return False
        if label == "person":
            return distance <= 1.0
        return distance <= self.emergency_distance

    def mark_seen(self, label):
        """Objektet syns men ska inte utvärderas nu (t.ex. ett akut objekt som inte är närmast)."""
        self.last_seen_timestamps[label] = time.time()
        self.rejection_counts[f"{label}:not_nearest"] += 1

    def evaluate_object(self, label, distance):
        """
        Utvärderar ett objekts status mot rådande säkerhetsregler (YOLO).
        Returnerar: (should_notify, is_emergency, priority)
        Priority: 1 = Akut, 2 = Navigering/Viktigt, 3 = Standard
        """
        if label in self.blacklist:
            self.rejection_counts[f"{label}:blacklist"] += 1
            return False, False, 3

        current_time = time.time()
        
        last_spoken = self.last_spoken_timestamps.get(label, 0)
        last_distance = self.last_distances.get(label, 0.0)
        last_seen = self.last_seen_timestamps.get(label, 0)
        
        dist_diff = abs(distance - last_distance)
        was_away = (current_time - last_seen) > 3.0 if last_seen > 0 else True
        
        self.last_seen_timestamps[label] = current_time

        # SÄKERHETSREGEL 1: AKUT VARNING (Nivå 1)
        if self.is_emergency_candidate(label, distance):
            came_closer = (last_distance - distance) > self.emergency_closer
            if was_away or came_closer or (current_time - last_spoken > self.emergency_repeat):
                self._update_object_state(label, distance, current_time)
                return True, True, 1
            self.rejection_counts[f"{label}:emergency_cooldown"] += 1
            return False, False, 1

        # SÄKERHETSREGEL 2: STANDARD LOGIK (Nivå 2 eller 3)
        per_label_cooldown_passed = (current_time - last_spoken) > self.cooldown
        global_pacing_passed = (current_time - self.global_last_spoken_time) > 2.5
        is_new_or_moved = was_away or dist_diff > self.dist_threshold
        
        if is_new_or_moved and per_label_cooldown_passed and global_pacing_passed:
            self._update_state_global(current_time)
            self._update_object_state(label, distance, current_time)
            
            # COCO saknar dörrar/trappor, så YOLO-objekt är alltid nivå 3 (trappor sköts av evaluate_stair_drop)
            return True, False, 3
            
        # TELEMETRI: Logga varför det blockerades
        if not per_label_cooldown_passed:
            self.rejection_counts[f"{label}:cooldown"] += 1
        elif not global_pacing_passed:
            self.rejection_counts["global_pacing"] += 1
        elif not is_new_or_moved:
            self.rejection_counts[f"{label}:not_moved"] += 1

        return False, False, 3

    def log_summary_if_needed(self):
        """Skickar filterdata till telemetrin var 5:e sekund för att undvika spam"""
        now = time.time()
        if now - self.last_summary_time > 5.0:
            if self.rejection_counts:
                telemetry.log("filter_summary", counts=dict(self.rejection_counts))
                self.rejection_counts.clear()
            self.last_summary_time = now

    def evaluate_stair_drop(self, z_val):
        """
        Analyserar golvytan i realtid. 
        Har nu ett övre tak (1.8m) för att undvika falsklarm från himmel/glitchar.
        """
        if z_val <= 0.1:
            if z_val == 0 and 0.1 < self.last_ground_z < 1.8:
                self.consecutive_stair_drops += 1
            else:
                self.consecutive_stair_drops = 0
                return False
        else:
            # Trapplogik: Golvet försvinner plötsligt, men inte mer än 1.8m
            if 0.1 < self.last_ground_z < 1.8 and 0.45 < (z_val - self.last_ground_z) < 1.8:
                self.consecutive_stair_drops += 1
            else:
                self.consecutive_stair_drops = 0

            self.last_ground_z = z_val

        # BRUSFILTER: Kräver 3 rutor i rad
        if self.consecutive_stair_drops >= 3:
            current_time = time.time()
            if current_time - self.last_stair_warning_time > 7.0:
                self.last_stair_warning_time = current_time
                self.consecutive_stair_drops = 0
                return True

        return False

    def _update_object_state(self, label, distance, current_time):
        self.last_spoken_timestamps[label] = current_time
        self.last_distances[label] = distance

    def update_stair_pacing(self, current_time):
        self.global_last_spoken_time = current_time

    def _update_state_global(self, current_time):
        self.global_last_spoken_time = current_time


class AudioSystem:
    def __init__(self):
        pass

    def speak(self, text, priority=3, t_detect=None, key=None):
        msg_id = telemetry.new_id()
        audio_system.speak(text, priority=priority, msg_id=msg_id, t_detect=t_detect, key=key)


class VisionSystem:
    def __init__(self, confidence_threshold=0.35):
        self.pipeline = dai.Pipeline()
        self.label_map = [
            "person", "cykel", "bil", "motorcykel", "flygplan", "buss", "tåg", "lastbil", "båt",
            "trafikljus", "brandpost", "stoppskylt", "parkeringsmätare", "bänk", "fågel", "katt",
            "hund", "häst", "får", "ko", "elefant", "björn", "zebra", "giraff", "ryggsäck",
            "paraply", "handväska", "slips", "resväska", "frisbee", "skidor", "snowboard",
            "sportboll", "drake", "basebollträ", "basebollhandske", "skateboard", "surfbräda",
            "tennisracket", "flaska", "vinglas", "kopp", "gaffel", "kniv", "sked", "skål",
            "banan", "äpple", "smörgås", "apelsin", "broccoli", "morot", "varmkorv", "pizza",
            "munk", "tårta", "stol", "soffa", "krukväxt", "säng", "matbord", "toalett",
            "tv", "bärbar dator", "datormus", "fjärrkontroll", "tangentbord", "mobiltelefon",
            "mikrovågsugn", "ugn", "brödrost", "diskho", "kylskåp", "bok", "klocka",
            "vas", "sax", "nalle", "hårtork", "tandborste"
        ]
        self._setup_pipeline(confidence_threshold)
        
    def _setup_pipeline(self, threshold):
        cam_rgb = self.pipeline.create(dai.node.ColorCamera)
        left = self.pipeline.create(dai.node.MonoCamera)
        right = self.pipeline.create(dai.node.MonoCamera)
        stereo = self.pipeline.create(dai.node.StereoDepth)
        spatial_nn = self.pipeline.create(dai.node.YoloSpatialDetectionNetwork)
        
        self.spatial_calc = self.pipeline.create(dai.node.SpatialLocationCalculator)
        xout_spatial_data = self.pipeline.create(dai.node.XLinkOut)
        xout_spatial_data.setStreamName("spatialData")

        spatial_nn.setConfidenceThreshold(threshold)
        spatial_nn.setNumClasses(80)
        spatial_nn.setCoordinateSize(4)
        spatial_nn.setIouThreshold(0.5)
        spatial_nn.setAnchors([10, 14, 23, 27, 37, 58, 81, 82, 135, 169, 344, 319])
        spatial_nn.setAnchorMasks({"side13": [0, 1, 2], "side26": [3, 4, 5]})
        spatial_nn.setBlobPath(blobconverter.from_zoo(name="yolov4_tiny_coco_416x416", zoo_type="depthai", shaves=5))
        spatial_nn.setBoundingBoxScaleFactor(0.5)

        cam_rgb.setPreviewSize(416, 416)  
        cam_rgb.setInterleaved(False)
        cam_rgb.setVideoSize(1920, 1080)

        left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

        configData = dai.SpatialLocationCalculatorConfigData()
        configData.roi = dai.Rect(dai.Point2f(0.46, 0.70), dai.Point2f(0.54, 0.85))
        self.spatial_calc.initialConfig.addROI(configData)

        left.out.link(stereo.left)
        right.out.link(stereo.right)
        cam_rgb.preview.link(spatial_nn.input)
        stereo.depth.link(spatial_nn.inputDepth)
        stereo.depth.link(self.spatial_calc.inputDepth)
        self.spatial_calc.out.link(xout_spatial_data.input)

        xout_det = self.pipeline.create(dai.node.XLinkOut)
        xout_det.setStreamName("detections")
        spatial_nn.out.link(xout_det.input)

        xout_video = self.pipeline.create(dai.node.XLinkOut)
        xout_video.setStreamName("video")
        cam_rgb.video.link(xout_video.input)

    def get_pipeline(self):
        return self.pipeline


class VisionGlasses:
    def __init__(self):
        self.vision = VisionSystem(confidence_threshold=0.35)
        self.filter = DetectionFilter()
        self.audio = AudioSystem()
        self.ai_service = GeminiService()
        
        self.is_gemini_processing = False
        self.gemini_lock = threading.Lock()
        
        self.last_gemini_trigger_time = 0.0
        # Antal bildrutor i rad där YOLO inte sett något. En enstaka tom bildruta
        # (YOLO tappar objektet en ruta) får inte trigga Gemini.
        self.empty_frames = 0

    def _call_gemini_async(self, frame, mode="navigation", priority=3):
        t_start = time.time()
        telemetry.log("gemini_start", trigger=mode)
        # Unikt filnamn för att undvika write-krockar om flera trådar startas
        img_path = f"/tmp/gemini_capture_{uuid.uuid4().hex[:8]}.jpg"
        try:
            small_frame = cv2.resize(frame, (1280, 720))
            cv2.imwrite(img_path, small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            
            answer = self.ai_service.analyze_frame(img_path, mode=mode)
            if answer:
                self.audio.speak(answer, priority=priority)
            
            telemetry.log("gemini_end", ok=True, duration=time.time() - t_start)
                
        except Exception as e:
            print(f"❌ Fel under asynkron Gemini-körning: {e}")
            telemetry.log("gemini_end", ok=False, duration=time.time() - t_start)
        finally:
            with self.gemini_lock:
                self.is_gemini_processing = False
            # Radera bilden: annars fylls /tmp (RAM) och bilder på personer ligger kvar
            try:
                os.remove(img_path)
            except OSError:
                pass

    def run(self):
        print("🚀 Vision-5 System startar (Säkerhets-, Trafik- och Intelligent OCR-läge)...")
        print("Systemet är live! Tryck på ENTER (eller din USB-knapp) när som helst.")
        
        with dai.Device(self.vision.get_pipeline()) as device:
            q_det = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
            q_video = device.getOutputQueue(name="video", maxSize=4, blocking=False)
            q_spatial = device.getOutputQueue(name="spatialData", maxSize=4, blocking=False)
            
            last_heartbeat = time.time()
            try:
                print("Kameran letar efter objekt och scannar av golvytan...")
                while True:
                    in_det = q_det.get()
                    t_detect = time.time() # <-- HÄR SKAPAS DEN SANNA TIDSSTÄMPELN
                    
                    detections = in_det.detections
                    self.empty_frames = self.empty_frames + 1 if len(detections) == 0 else 0
                    in_video = q_video.tryGet()
                    in_spatial = q_spatial.tryGet()
                    
                    # Kör filter-sammanfattningen till telemetrin
                    self.filter.log_summary_if_needed()

                    if time.time() - last_heartbeat > 2.0:
                        print(f"⏱️   Letar aktivt... (Hittade {len(detections)} objekt)")
                        last_heartbeat = time.time()

                    # 1. MANUELL TRIGGER VIA TANGENTBORD/KNAPP
                    if select.select([sys.stdin], [], [], 0)[0]:
                        sys.stdin.readline()  
                        with self.gemini_lock:
                            if not self.is_gemini_processing and in_video is not None:
                                self.is_gemini_processing = True
                                print("\n🔘 [FYSISK TRIGGER] Knapptryck! Startar OCR via Gemini...")
                                high_res_frame = in_video.getCvFrame()
                                threading.Thread(
                                    target=self._call_gemini_async, 
                                    args=(high_res_frame, "describe", 2), 
                                    daemon=True
                                ).start()

                    # 2. DIGITAL BLINDKÄPP & AUTOMATISK ANALYS
                    if in_spatial is not None:
                        spatial_data = in_spatial.getSpatialLocations()
                        for loc in spatial_data:
                            z_val = loc.spatialCoordinates.z / 1000.0  
                            
                            if self.filter.evaluate_stair_drop(z_val):
                                current_time = time.time()
                                print("🚨 [BLINDKÄPP] Detekterade verifierad nivåskillnad/nedåtsteg!")
                                self.audio.speak("Trappa ner.", priority=1, t_detect=t_detect, key="trappa")
                                self.filter.update_stair_pacing(current_time)
                            
                            # Automatisk Gemini-trigger (Cooldown höjd till 15 sek, skippar "analyserar"-spam)
                            with self.gemini_lock:
                                if 0.2 < z_val < 1.4 and self.empty_frames >= 10 and not self.is_gemini_processing:
                                    current_time = time.time()
                                    if current_time - self.last_gemini_trigger_time > 15.0 and in_video is not None:
                                        self.is_gemini_processing = True
                                        self.last_gemini_trigger_time = current_time
                                        print("\n🤖 [AUTOMATISK TRIGGER] Okänt hinder upptäckt! Konsulterar Gemini...")
                                        
                                        high_res_frame = in_video.getCvFrame()
                                        threading.Thread(
                                            target=self._call_gemini_async, 
                                            args=(high_res_frame, "navigation", 2), 
                                            daemon=True
                                        ).start()

                    # 3. REAL-TIDS YOLO-LOOP (Standardobjekt)
                    objects = []
                    for det in detections:
                        distance = det.spatialCoordinates.z / 1000
                        if distance > 0.1:
                            objects.append((self.vision.label_map[det.label], distance))

                    # Bara det NÄRMASTE akuta objektet får larma i varje bildruta.
                    # Flera samtidiga akutlarm hinner aldrig sägas och klipper bara varandra.
                    emergencies = [o for o in objects if self.filter.is_emergency_candidate(*o)]
                    nearest = min(emergencies, key=lambda o: o[1]) if emergencies else None

                    for obj in objects:
                        label, distance = obj
                        if obj in emergencies and obj is not nearest:
                            self.filter.mark_seen(label)
                            continue

                        should_notify, is_emergency, priority = self.filter.evaluate_object(label, distance)

                        if should_notify:
                            dist_str = f"{distance:.1f}".replace('.', ',')
                            # Korta fraser: varje ord i en akutvarning är latens
                            speech_text = f"{label.capitalize()}. {dist_str} meter."

                            # Skicka med sanna tiden in i ljudkön!
                            self.audio.speak(speech_text, priority=priority, t_detect=t_detect, key=label)

                    time.sleep(0.01)
            except KeyboardInterrupt:
                print("\nStänger ner systemet på ett säkert sätt...")
                telemetry.close()  # <-- Stänger loggern snyggt

if __name__ == "__main__":
    app = VisionGlasses()
    app.run()