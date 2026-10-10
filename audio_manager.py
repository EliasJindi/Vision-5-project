import queue
import threading
import subprocess
import time
import itertools
import os
from tts_engine import TTSEngine, wav_duration
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

        self.pw_proc = None
        self.current_priority = 99
        self.current_msg_id = None
        self.current_start_time = 0.0

        # Per label spelas bara det NYASTE köade akutlarmet. Äldre larm för samma label slängs.
        self._latest_emergency_seq = {}

        # Piper körs hela tiden och vanliga fraser cachas som WAV (se tts_engine.py)
        self.tts = TTSEngine()

        self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.worker_thread.start()

    def prewarm(self, phrases):
        """Ladda röstmodellen i bakgrunden och rapportera hur stor del av fraserna som är cachade."""
        def run():
            t0 = time.time()
            self.tts.warm_up()
            missing = self.tts.missing(phrases)
            telemetry.log("tts_prewarm", phrases=len(phrases), missing=len(missing), duration=time.time() - t0)
            print(f"🗣️  [TTS] Röstmodell laddad ({time.time() - t0:.1f} s). "
                  f"{len(phrases) - len(missing)} av {len(phrases)} akutfraser i cache.")
            if missing:
                print("    Saknade fraser genereras när de behövs (~0,5 s första gången).")
                print("    Generera alla i förväg, UTAN kameran igång: python3 tts_engine.py --prewarm")
        threading.Thread(target=run, daemon=True).start()

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
                playing = self.pw_proc is not None and self.current_msg_id is not None
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
        return [self.pw_proc] if self.pw_proc else []

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

    def _is_stale(self, priority, seq, key, t_detect, msg_id, text):
        """Kollas både innan och efter syntesen: under syntesen kan läget ha ändrats."""
        age = time.time() - t_detect
        if age > TTL_PER_PRIORITY.get(priority, 4.0):
            print(f"[{time.strftime('%H:%M:%S')}] ⏳ [AudioQueue] Klipper inaktuellt ljud ({age:.1f}s gammalt): '{text}'")
            telemetry.log("speak_dropped", id=msg_id, reason="ttl", age=age)
            return True
        # Ett nyare akutlarm för samma sak har köats: det här är redan inaktuellt
        if priority == 1 and seq < self._latest_emergency_seq.get(key, -1):
            telemetry.log("speak_dropped", id=msg_id, reason="superseded", age=age)
            return True
        return False

    def _emergency_waiting(self):
        with self.queue.mutex:
            return bool(self.queue.queue) and self.queue.queue[0][0] == 1

    def _audio_worker(self):
        while True:
            try:
                item = self.queue.get()
                priority, seq, msg_id, t_detect, text, key = item

                if self._is_stale(priority, seq, key, t_detect, msg_id, text):
                    self.queue.task_done()
                    continue

                # LOGG: Workern börjar jobba med meddelandet
                telemetry.log("speak_start", id=msg_id)

                # 1. Hämta ljudfil: från cachen (direkt) eller via Piper som redan är igång
                cacheable = priority != 2  # Nivå 2 = Gemini-svar, unika varje gång
                t_synth = time.time()
                wav, cache_hit, temporary = self.tts.get_wav(text, cacheable=cacheable)
                if wav is None:
                    print(f"❌ [AudioQueue] Talsyntesen misslyckades: '{text}'")
                    telemetry.log("speak_error", id=msg_id, error="tts_failed")
                    self.queue.task_done()
                    continue

                # 2. Har något blivit viktigare/inaktuellt medan vi syntetiserade?
                if self._is_stale(priority, seq, key, t_detect, msg_id, text):
                    self._cleanup(wav, temporary)
                    self.queue.task_done()
                    continue
                if priority > 1 and self._emergency_waiting():
                    # Lägg tillbaka (samma seq, samma plats i kön). Filen är redan cachad.
                    self._cleanup(wav, temporary)
                    self.queue.put(item)
                    self.queue.task_done()
                    continue

                # 3. Spela upp
                duration = wav_duration(wav) or 5.0
                with self.lock:
                    try:
                        self.pw_proc = subprocess.Popen(
                            ["pw-play", wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                        )
                    except Exception as e:
                        print(f"❌ [AudioQueue] Kunde inte starta pw-play: {e}")
                        telemetry.log("speak_error", id=msg_id, error=str(e))
                        self.pw_proc = None
                        self._cleanup(wav, temporary)
                        self.queue.task_done()
                        continue
                    self.current_priority = priority
                    self.current_msg_id = msg_id
                    self.current_start_time = time.time()
                    pw_proc = self.pw_proc

                # LOGG: Ljudet börjar (detta är den ärliga latensen: detektion -> ljud)
                telemetry.log("audio_start", id=msg_id, cache_hit=cache_hit,
                              synth_s=round(self.current_start_time - t_synth, 3),
                              audio_s=round(duration, 2))

                try:
                    pw_proc.wait(timeout=duration + 3.0)
                except subprocess.TimeoutExpired:
                    print("⚠️ [AudioQueue] Pw-play hängde sig. Tvingar avslutning.")
                    with self.lock:
                        procs = self._detach_current("timeout") if self.pw_proc is pw_proc else []
                    self._kill(procs or [pw_proc])

                # LOGG: Uppspelning klar
                telemetry.log("speak_end", id=msg_id)

                with self.lock:
                    # Nollställ bara om ingen annan redan tagit över
                    if self.pw_proc is pw_proc:
                        self.pw_proc = None
                        self.current_priority = 99
                        self.current_msg_id = None

                self._cleanup(wav, temporary)
                self.queue.task_done()

            except Exception as e:
                print(f"Fel i audio worker: {e}")
                time.sleep(0.1)

    @staticmethod
    def _cleanup(wav, temporary):
        if temporary:
            try:
                os.remove(wav)
            except OSError:
                pass


audio_system = AudioManager()
# Starta övervakning av värme, spänning och köstorlek (1 gång per sekund)
telemetry.start_vitals(qsize_fn=audio_system.queue.qsize, interval=1.0)
