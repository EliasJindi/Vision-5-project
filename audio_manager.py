import queue
import threading
import subprocess
import time
import itertools
from telemetry_logger import telemetry  # <-- Telemetri importerad

class AudioManager:
    def __init__(self):
        self.queue = queue.PriorityQueue()
        self._counter = itertools.count()
        self.lock = threading.Lock()
        
        self.piper_proc = None
        self.pw_proc = None
        self.current_priority = 99
        self.current_msg_id = None  # <-- Håller koll på vad som spelas just nu
        
        self.piper_path = "./piper/piper"
        self.model_path = "sv_SE-alma-medium.onnx"
        
        self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, text: str, priority: int = 3, msg_id=None, t_detect=None):
        if msg_id is None:
            msg_id = telemetry.new_id()
        if t_detect is None:
            t_detect = time.time()
            
        time_str = time.strftime('%H:%M:%S')
        print(f"[{time_str}] 🔊 [AudioQueue] Lägger till nivå {priority}: '{text}'")
        
        # LOGG: Meddelande skapat
        telemetry.log("speak_enqueued", id=msg_id, priority=priority, text=text, t_detect=t_detect)
        
        with self.lock:
            if priority == 1 and self.current_priority > 1 and (self.piper_proc or self.pw_proc):
                print(f"[{time_str}] 🚨 [AudioQueue] AKUT VARNING! Klipper pågående ljud.")
                self.stop_current()

        # Lägg in msg_id och t_detect i kön
        self.queue.put((priority, next(self._counter), msg_id, t_detect, text))

    def stop_current(self):
        # LOGG: Ljud avbröts av akut varning
        if self.current_msg_id:
            telemetry.log("speak_interrupted", id=self.current_msg_id)
            
        if self.pw_proc:
            try: self.pw_proc.terminate()
            except Exception: pass
        if self.piper_proc:
            try: self.piper_proc.terminate()
            except Exception: pass

    def _audio_worker(self):
        while True:
            try:
                # Packa upp all data
                priority, _, msg_id, t_detect, text = self.queue.get()
                
                # BÄST-FÖRE-SPÄRR (Nu mätt från exakt när kameran såg objektet!)
                age = time.time() - t_detect
                if priority > 1 and age > 4.0:
                    print(f"[{time.strftime('%H:%M:%S')}] ⏳ [AudioQueue] Klipper inaktuellt ljud ({age:.1f}s gammalt): '{text}'")
                    telemetry.log("speak_dropped", id=msg_id, reason="ttl", age=age)
                    self.queue.task_done()
                    continue
                
                with self.lock:
                    self.current_priority = priority
                    self.current_msg_id = msg_id
                    
                    # LOGG: Uppspelning börjar
                    telemetry.log("speak_start", id=msg_id)
                    
                    self.piper_proc = subprocess.Popen(
                        [self.piper_path, "--model", self.model_path, "--output_file", "-"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL
                    )
                    
                    self.pw_proc = subprocess.Popen(
                        ["pw-play", "-"],
                        stdin=self.piper_proc.stdout,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
                    self.piper_proc.stdout.close()
                
                try:
                    self.piper_proc.stdin.write((text + "\n").encode('utf-8'))
                    self.piper_proc.stdin.close()
                except Exception:
                    pass
                
                try:
                    self.pw_proc.wait(timeout=15)
                    self.piper_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("⚠️ [AudioQueue] Pw-play hängde sig. Tvingar avslutning.")
                    with self.lock:
                        self.stop_current()
                
                # LOGG: Uppspelning klar
                telemetry.log("speak_end", id=msg_id)
                
                with self.lock:
                    self.piper_proc = None
                    self.pw_proc = None
                    self.current_priority = 99
                    self.current_msg_id = None
                
                self.queue.task_done()
                
            except Exception as e:
                print(f"Fel i audio worker: {e}")
                time.sleep(0.1)

audio_system = AudioManager()
# Starta övervakning av värme och köstorlek
telemetry.start_vitals(qsize_fn=audio_system.queue.qsize)