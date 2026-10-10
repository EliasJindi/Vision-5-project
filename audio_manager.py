import queue
import threading
import subprocess
import time
import itertools
from telemetry_logger import telemetry  # <-- Telemetri importerad

# Bäst-före per nivå (sekunder i kön räknat från t_detect).
# Nivå 1 kort: en gammal akutvarning är fel information.
# Nivå 2 lång: Gemini-svar som användaren själv bett om ska inte slängas i onödan.
TTL_PER_PRIORITY = {1: 2.0, 2: 8.0, 3: 4.0}

# Ett nytt akutlarm får bara klippa ett pågående akutlarm om det har hunnit spelas
# så här länge. Annars hackar två samtidiga larm (t.ex. person + bil) sönder varandra
# och användaren hör aldrig ett helt ord.
MIN_EMERGENCY_PLAY_S = 0.7


class AudioManager:
    def __init__(self):
        self.queue = queue.PriorityQueue()
        self._counter = itertools.count()
        self.lock = threading.Lock()

        self.piper_proc = None
        self.pw_proc = None
        self.current_priority = 99
        self.current_msg_id = None
        self.current_start_time = 0.0

        # Per label spelas bara det NYASTE köade akutlarmet. Äldre larm för samma label slängs.
        self._latest_emergency_seq = {}

        self.piper_path = "./piper/piper"
        self.model_path = "sv_SE-alma-medium.onnx"

        self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, text: str, priority: int = 3, msg_id=None, t_detect=None, key=None):
        if msg_id is None:
            msg_id = telemetry.new_id()
        if t_detect is None:
            t_detect = time.time()
        if key is None:
            key = text

        time_str = time.strftime('%H:%M:%S')
        print(f"[{time_str}] 🔊 [AudioQueue] Lägger till nivå {priority}: '{text}'")

        # LOGG: Meddelande skapat
        telemetry.log("speak_enqueued", id=msg_id, priority=priority, text=text, t_detect=t_detect)

        seq = next(self._counter)
        procs_to_stop = []
        with self.lock:
            if priority == 1:
                self._latest_emergency_seq[key] = seq
                # current_msg_id är None om ljudet redan klippts men workern inte hunnit städa
                playing = (self.piper_proc or self.pw_proc) and self.current_msg_id is not None
                played_for = time.time() - self.current_start_time
                if playing and (self.current_priority > 1 or played_for >= MIN_EMERGENCY_PLAY_S):
                    print(f"[{time_str}] 🚨 [AudioQueue] AKUT VARNING! Klipper pågående ljud.")
                    procs_to_stop = self._detach_current("emergency")

        # Döda processerna UTANFÖR låset så att kameraloopen aldrig väntar på dem
        self._kill(procs_to_stop)

        self.queue.put((priority, seq, msg_id, t_detect, text, key))

    def _detach_current(self, reason):
        """Måste anropas med self.lock. Returnerar processerna som ska dödas."""
        if self.current_msg_id is not None:
            telemetry.log("speak_interrupted", id=self.current_msg_id, reason=reason)
        self.current_msg_id = None  # Samma ljud ska inte kunna klippas (och loggas) två gånger
        procs = [p for p in (self.pw_proc, self.piper_proc) if p]
        return procs

    @staticmethod
    def _kill(procs):
        """terminate() först, kill() om processen inte dör inom 0,3 s."""
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in procs:
            try:
                proc.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    proc.wait(timeout=0.3)
                except Exception:
                    pass
            except Exception:
                pass

    def stop_current(self):
        with self.lock:
            procs = self._detach_current("manual")
        self._kill(procs)

    @staticmethod
    def _play_timeout(text):
        # Ungefär 12 tecken per sekund i Piper + marginal, så att långa Gemini-svar inte klipps
        return 3.0 + len(text) / 10.0

    def _audio_worker(self):
        while True:
            try:
                # Packa upp all data
                priority, seq, msg_id, t_detect, text, key = self.queue.get()

                # BÄST-FÖRE-SPÄRR (mätt från när kameran såg objektet)
                age = time.time() - t_detect
                ttl = TTL_PER_PRIORITY.get(priority, 4.0)
                if age > ttl:
                    print(f"[{time.strftime('%H:%M:%S')}] ⏳ [AudioQueue] Klipper inaktuellt ljud ({age:.1f}s gammalt): '{text}'")
                    telemetry.log("speak_dropped", id=msg_id, reason="ttl", age=age)
                    self.queue.task_done()
                    continue

                # Ett nyare akutlarm för samma sak har köats: det här är redan inaktuellt
                if priority == 1 and seq < self._latest_emergency_seq.get(key, -1):
                    telemetry.log("speak_dropped", id=msg_id, reason="superseded", age=age)
                    self.queue.task_done()
                    continue

                with self.lock:
                    self.current_priority = priority
                    self.current_msg_id = msg_id
                    self.current_start_time = time.time()

                    # LOGG: Uppspelning börjar
                    telemetry.log("speak_start", id=msg_id)

                    try:
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
                    except Exception as e:
                        # Om pw-play inte startar får Piper inte bli kvar som zombie
                        print(f"❌ [AudioQueue] Kunde inte starta ljud: {e}")
                        telemetry.log("speak_error", id=msg_id, error=str(e))
                        self._kill([p for p in (self.piper_proc,) if p])
                        self.piper_proc = None
                        self.pw_proc = None
                        self.current_priority = 99
                        self.current_msg_id = None
                        self.queue.task_done()
                        continue

                    piper_proc, pw_proc = self.piper_proc, self.pw_proc

                try:
                    piper_proc.stdin.write((text + "\n").encode('utf-8'))
                    piper_proc.stdin.close()
                except Exception:
                    pass

                try:
                    pw_proc.wait(timeout=self._play_timeout(text))
                    piper_proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("⚠️ [AudioQueue] Pw-play hängde sig. Tvingar avslutning.")
                    with self.lock:
                        procs = self._detach_current("timeout") if self.pw_proc is pw_proc else []
                    self._kill(procs or [pw_proc, piper_proc])

                # LOGG: Uppspelning klar
                telemetry.log("speak_end", id=msg_id)

                with self.lock:
                    # Nollställ bara om ingen annan redan tagit över
                    if self.pw_proc is pw_proc:
                        self.piper_proc = None
                        self.pw_proc = None
                        self.current_priority = 99
                        self.current_msg_id = None

                self.queue.task_done()

            except Exception as e:
                print(f"Fel i audio worker: {e}")
                time.sleep(0.1)


audio_system = AudioManager()
# Starta övervakning av värme, spänning och köstorlek (1 gång per sekund)
telemetry.start_vitals(qsize_fn=audio_system.queue.qsize, interval=1.0)
