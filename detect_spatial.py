import depthai as dai
import blobconverter
import subprocess
import time
import threading
import cv2
import sys
import select

# Importera din fristående AI-modul enligt modularitetsprincipen
from gemini_service import GeminiService

class DetectionFilter:
    """
    ANSVAR: Hanterar filtrering av oviktiga objekt (Blacklist) samt beräknar
    om ett högprioriterat objekt kräver omedelbar akut-varning eller följer vanlig cooldown.
    """
    def __init__(self, cooldown_seconds=3.0, distance_threshold_meters=0.4, emergency_distance_meters=3.0):
        self.cooldown = cooldown_seconds
        self.dist_threshold = distance_threshold_meters
        self.emergency_distance = emergency_distance_meters
        
        self.last_spoken_time = 0
        self.last_label = ""
        self.last_distance = 0.0

        # Spåra när vi senast såg ett objekt för att hantera "tappat bort"-logik
        self.last_seen_timestamps = {}

        # Sortera bort spökdetektioner och orelevanta inomhusobjekt utomhus
        self.blacklist = {"flygplan", "paraply", "frisbee", "drake", "slips", "sportboll", "handvaska"}
        
        # Högprioriterade trafikobjekt (Liv och död vid utomhusnavigering)
        self.high_priority = {"bil", "buss", "lastbil", "motorcykel", "cykel", "trafikljus", "stoppskylt"}

    def evaluate(self, label, distance):
        """
        Utvärderar ett objekts status mot rådande säkerhetsregler.
        Returnerar: (should_notify, is_emergency)
        """
        if label in self.blacklist:
            return False, False

        current_time = time.time()
        dist_diff = abs(distance - self.last_distance)
        
        # Kolla om objektet har varit helt borta från kamerans synfält i mer än 2.0 sekunder
        last_seen = self.last_seen_timestamps.get(label, 0)
        was_away = (current_time - last_seen) > 2.0 if last_seen > 0 else True
        
        self.last_seen_timestamps[label] = current_time
        
        # SÄKERHETSREGEL 1: AKUT TRAFIKVARNING
        if label in self.high_priority and distance <= self.emergency_distance:
            if (label != self.last_label) or (dist_diff > 0.3) or was_away or (current_time - self.last_spoken_time > 0.8):
                self._update_state(label, distance, current_time)
                return True, True

        # SÄKERHETSREGEL 2: STANDARDLOGIK
        is_new_or_moved = (label != self.last_label) or (dist_diff > self.dist_threshold) or was_away
        cooldown_passed = (current_time - self.last_spoken_time) > self.cooldown
        
        if is_new_or_moved and cooldown_passed:
            self._update_state(label, distance, current_time)
            return True, False
            
        return False, False

    def _update_state(self, label, distance, current_time):
        """Hjälpmetod för att uppdatera filtertillståndet enligt DRY-principen."""
        self.last_spoken_time = current_time
        self.last_label = label
        self.last_distance = distance


class AudioSystem:
    """
    ANSVAR: Äger det rena gränssnittet mot operativsystemets ljudenheter.
    Syntetiserar inskickad sträng till tal via Piper och spelar upp via PipeWire.
    """
    def __init__(self):
        self.piper_path = "./piper/piper"
        self.model_path = "sv_SE-alma-medium.onnx"

    def speak(self, text):
        """Tar emot en färdigformaterad textsträng och strömmar en WAV-fil via pw-play."""
        print(f"🔊 Alma säger: {text}")
        
        command = (
            f'echo "{text}" | {self.piper_path} --model {self.model_path} --output_file - '
            f'| pw-play -'
        )
        
        try:
            # Popen körs asynkront i bakgrunden så att kamerasynen aldrig laggar
            subprocess.Popen(command, shell=True)
        except Exception as e:
            print(f"❌ Fel i ljudsystemet (Piper/pw-play): {e}")


class VisionSystem:
    """
    ANSVAR: Bygger, konfigurerar och äger OAK-D-kamerans hårdvarupipeline 
    för 3D-djupberäkning och Dual-Stream (YOLO + Högupplöst Video).
    """
    def __init__(self, confidence_threshold=0.35):
        self.pipeline = dai.Pipeline()
        self.label_map = [
            "person", "cykel", "bil", "motorcykel", "flygplan", "buss", "tag", "lastbil", "bat", 
            "trafikljus", "brandpost", "stoppskylt", "parkeringsmatare", "bank", "fagel", "katt", 
            "hund", "hast", "far", "ko", "elefant", "bjorn", "zebra", "giraff", "ryggsack", 
            "paraply", "handvaska", "slips", "resvaska", "frisbee", "skidor", "snowboard", 
            "sportboll", "drake", "basebolltradd", "basebollhandske", "skateboard", "surfbrada", 
            "tennisracket", "flaska", "vinglas", "kopp", "gaffel", "kniv", "sked", "skal", 
            "banan", "apple", "smorgas", "apelsin", "broccoli", "morot", "varmkorv", "pizza", 
            "donut", "tarta", "stol", "soffa", "krukvast", "sang", "matbord", "toalett", 
            "tv-skarm", "barbar dator", "datormus", "fjarrkontroll", "tangentbord", "mobiltelefon", 
            "mikrovagsugn", "ugn", "brodroster", "diskho", "kylskap", "bok", "klocka", 
            "vas", "sax", "nallebjorn", "hartork", "tandborste"
        ]
        self._setup_pipeline(confidence_threshold)
        
    def _setup_pipeline(self, threshold):
        cam_rgb = self.pipeline.create(dai.node.ColorCamera)
        left = self.pipeline.create(dai.node.MonoCamera)
        right = self.pipeline.create(dai.node.MonoCamera)
        stereo = self.pipeline.create(dai.node.StereoDepth)
        spatial_nn = self.pipeline.create(dai.node.YoloSpatialDetectionNetwork)
        
        # YOLOv4-Tiny hårdvarukonfiguration
        spatial_nn.setConfidenceThreshold(threshold)
        spatial_nn.setNumClasses(80)
        spatial_nn.setCoordinateSize(4)
        spatial_nn.setIouThreshold(0.5)
        spatial_nn.setAnchors([10, 14, 23, 27, 37, 58, 81, 82, 135, 169, 344, 319])
        spatial_nn.setAnchorMasks({"side13": [0, 1, 2], "side26": [3, 4, 5]})
        spatial_nn.setBlobPath(blobconverter.from_zoo(name="yolov4_tiny_coco_416x416", zoo_type="depthai", shaves=5))
        spatial_nn.setBoundingBoxScaleFactor(0.5)

        # STRÖM 1: Synkronisera kamerasensorerna till 416x416 pixlar för YOLO
        cam_rgb.setPreviewSize(416, 416)  
        cam_rgb.setInterleaved(False)
        
        # STRÖM 2: Konfigurera videoströmmen till Full HD (1080p) för moln-OCR
        cam_rgb.setVideoSize(1920, 1080)

        left.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        right.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)

        # Länka ihop hårdvarunoderna på kamerans chip
        left.out.link(stereo.left)
        right.out.link(stereo.right)
        cam_rgb.preview.link(spatial_nn.input)
        stereo.depth.link(spatial_nn.inputDepth)

        # Skapa XLink-utgångskö för YOLO-detektioner till Pajen
        xout_det = self.pipeline.create(dai.node.XLinkOut)
        xout_det.setStreamName("detections")
        spatial_nn.out.link(xout_det.input)

        # Skapa XLink-utgångskö för 1080p-videorutor till Pajen
        xout_video = self.pipeline.create(dai.node.XLinkOut)
        xout_video.setStreamName("video")
        cam_rgb.video.link(xout_video.input)

    def get_pipeline(self):
        return self.pipeline


class VisionGlasses:
    """
    ANSVAR: Fungerar som applikationsorkestrator. Startar enheten, läser dataköerna, 
    fångar hårdvaruklick icke-blockerande och skickar asynkrona anrop till GeminiService.
    """
    def __init__(self):
        self.vision = VisionSystem(confidence_threshold=0.35)
        self.filter = DetectionFilter(cooldown_seconds=3.0, distance_threshold_meters=0.4, emergency_distance_meters=3.0)
        self.audio = AudioSystem()
        
        # Instansiera den fristående Gemini-modulen (Lös koppling)
        self.ai_service = GeminiService()
        self.is_gemini_processing = False

    def _call_gemini_async(self, frame):
        """Metod som körs i en bakgrundstråd för att skydda realtidsloopen mot nätverks-lagg."""
        self.is_gemini_processing = True
        try:
            img_path = "gemini_capture.jpg"
            cv2.imwrite(img_path, frame)

            # Skicka bilden till den externa servicen
            answer = self.ai_service.analyze_frame(img_path)
            self.audio.speak(answer)

        except Exception as e:
            print(f"❌ Fel under asynkrons Gemini-körning: {e}")
        finally:
            self.is_gemini_processing = False

    def run(self):
        print("🚀 Vision-5 System startar (Säkerhets-, Trafik- och Intelligent OCR-läge)...")
        print("Systemet är live! Tryck på ENTER (eller din USB-knapp) när som helst.")
        
        with dai.Device(self.vision.get_pipeline()) as device:
            q_det = device.getOutputQueue(name="detections", maxSize=4, blocking=False)
            q_video = device.getOutputQueue(name="video", maxSize=4, blocking=False)
            
            last_heartbeat = time.time()
            try:
                print("Kameran letar efter objekt...")
                while True:
                    in_det = q_det.get()
                    detections = in_det.detections
                    
                    # Hämta den senaste högupplösta videorutan (icke-blockerande)
                    in_video = q_video.tryGet()

                    # Hjärtslag / Debug-indikator
                    if time.time() - last_heartbeat > 2.0:
                        print(f"⏱️  Letar aktivt... (Hittade {len(detections)} objekt i denna bildruta)")
                        last_heartbeat = time.time()

                    # ICKE-BLOCKERANDE TANGENTBORDSLYSSNARE (select-multiplexering)
                    if select.select([sys.stdin], [], [], 0)[0]:
                        sys.stdin.readline()  # Rensa bort Enter-trycket ur bufferten
                        
                        if not self.is_gemini_processing and in_video is not None:
                            print("\n🔘 [FYSISK TRIGGER] Knapptryck registrerat! Aktiverar intelligent OCR via Gemini...")
                            high_res_frame = in_video.getCvFrame()
                            
                            # Starta molntjänsten i en daemon-tråd
                            threading.Thread(target=self._call_gemini_async, args=(high_res_frame,), daemon=True).start()

                    # REAL-TIDS YOLO-LOOP
                    for det in detections:
                        label = self.vision.label_map[det.label]
                        distance = det.spatialCoordinates.z / 1000  
                        
                        if distance > 0.1:
                            should_notify, is_emergency = self.filter.evaluate(label, distance)
                            
                            if should_notify:
                                dist_str = f"{distance:.1f}".replace('.', ',')
                                
                                if is_emergency:
                                    speech_text = f"Akut varning. {label} nära. {dist_str} meter."
                                else:
                                    speech_text = f"{label}. {dist_str} meter."
                                    
                                self.audio.speak(speech_text)
                    
                    time.sleep(0.01)
            except KeyboardInterrupt:
                print("\nStänger ner systemet på ett säkert sätt...")

if __name__ == "__main__":
    app = VisionGlasses()
    app.run()