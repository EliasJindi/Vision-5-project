# ===================== NY FIL AV CLAUDE (2026-10-10) =====================
# Piper körs som EN process (--json-input) och färdiga fraser sparas i cache/tts/.
# PIPER_CPUS begränsar Piper till 2 kärnor (Pi:n dog av strömbrist med alla 4).
# Kör "python3 tts_engine.py --prewarm" för att generera akutfraserna i förväg.
# =========================================================================
"""
tts_engine.py - Piper som körs hela tiden + cache av färdiga ljudfiler.

Varför: att starta Piper per meddelande laddar röstmodellen varje gång
(uppmätt 0,85 s på Pi 5) innan ett enda ljud hörs. Här laddas modellen EN gång,
och vanliga fraser ("Bil. 0,6 meter.") sparas som WAV-filer som spelas direkt.
"""
import hashlib
import json
import os
import select
import shutil
import struct
import subprocess
import threading
import time
import uuid

PIPER_PATH = "./piper/piper"
MODEL_PATH = "sv_SE-alma-medium.onnx"
CACHE_DIR = "cache/tts"

# Talhastighet: 1.0 = normal, lägre = snabbare (0.85 ≈ 15 % snabbare). Gäller även Gemini-svar.
LENGTH_SCALE = 0.85
# Piper får bara använda dessa CPU-kärnor. Med alla fyra blir strömtopparna så höga
# att Pi:n kan dö på powerbank. Kärna 0-1 lämnas åt kameraloopen.
PIPER_CPUS = "2,3"

# Tystnad efter varje mening (Piper-standard 0.2 s). "Bil. 0,6 meter." är två meningar.
SENTENCE_SILENCE = 0.05


def wav_duration(path):
    """Längd i sekunder, eller None om filen inte är en komplett WAV ännu."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            header = f.read(44)
        if len(header) < 44 or header[:4] != b"RIFF":
            return None
        riff_size = struct.unpack("<I", header[4:8])[0]
        if size < riff_size + 8:
            return None  # Piper har inte skrivit klart filen
        channels = struct.unpack("<H", header[22:24])[0]
        rate = struct.unpack("<I", header[24:28])[0]
        bits = struct.unpack("<H", header[34:36])[0]
        data_size = struct.unpack("<I", header[40:44])[0]
        return data_size / (rate * channels * bits / 8)
    except (OSError, struct.error, ZeroDivisionError):
        return None


class TTSEngine:
    def __init__(self, length_scale=LENGTH_SCALE, sentence_silence=SENTENCE_SILENCE):
        self.length_scale = length_scale
        self.sentence_silence = sentence_silence
        self._lock = threading.Lock()
        self._proc = None
        self._persistent_failures = 0
        # Antal levande meddelanden som väntar på syntes. Förgenereringen pausar så länge
        # det är > 0, så att ett akutlarm aldrig hamnar bakom 200 fraser i bakgrunden.
        self._live_waiting = 0
        os.makedirs(CACHE_DIR, exist_ok=True)

    # ---------- publikt API ----------
    def cache_path(self, text):
        key = f"{MODEL_PATH}|{self.length_scale}|{self.sentence_silence}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".wav")

    def get_wav(self, text, cacheable=True):
        """
        Returnerar (sökväg, cache_hit, temporär). Sökvägen är None om syntesen misslyckades.
        Temporära filer (t.ex. Gemini-svar) ska raderas av den som spelat upp dem.
        """
        if cacheable:
            path = self.cache_path(text)
            if wav_duration(path) is not None:
                return path, True, False
        else:
            path = f"/tmp/tts_{uuid.uuid4().hex[:8]}.wav"

        ok = self.synthesize(text, path)
        return (path if ok else None), False, not cacheable

    @property
    def persistent_works(self):
        return self._persistent_failures < 3

    def synthesize(self, text, path, timeout=10.0, background=False):
        if background:
            while self._live_waiting > 0:
                time.sleep(0.02)
        else:
            self._live_waiting += 1
        try:
            return self._synthesize_locked(text, path, timeout)
        finally:
            if not background:
                self._live_waiting -= 1

    def _synthesize_locked(self, text, path, timeout):
        with self._lock:
            if self._persistent_failures < 3 and self._synth_persistent(text, path, timeout):
                return True
            # Reserv: gamla sättet (en Piper per meddelande). Långsamt men beprövat.
            return self._synth_oneshot(text, path, timeout)

    def warm_up(self):
        """Laddar röstmodellen direkt vid start i stället för vid första larmet."""
        self.synthesize("Start.", "/tmp/tts_warmup.wav", background=True)

    # ---------- internt ----------
    def missing(self, phrases):
        return [t for t in phrases if wav_duration(self.cache_path(t)) is None]

    def _base_args(self):
        pin = ["taskset", "-c", PIPER_CPUS] if PIPER_CPUS and shutil.which("taskset") else []
        return pin + [PIPER_PATH, "--model", MODEL_PATH,
                "--length_scale", str(self.length_scale),
                "--sentence_silence", str(self.sentence_silence)]

    def _synth_persistent(self, text, path, timeout):
        try:
            if self._proc is None or self._proc.poll() is not None:
                self._proc = subprocess.Popen(
                    self._base_args() + ["--json-input"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
            line = json.dumps({"text": text, "output_file": os.path.abspath(path)}, ensure_ascii=False)
            self._proc.stdin.write((line + "\n").encode("utf-8"))
            self._proc.stdin.flush()

            deadline = time.time() + timeout
            while time.time() < deadline:
                ready, _, _ = select.select([self._proc.stdout], [], [], max(0.0, deadline - time.time()))
                if not ready:
                    break
                out = self._proc.stdout.readline()
                if not out:
                    break  # Piper dog
                if out.decode("utf-8", "replace").strip() == os.path.abspath(path):
                    if self._wait_complete(path):
                        self._persistent_failures = 0
                        return True
                    break
        except Exception:
            pass

        self._persistent_failures += 1
        self._stop_proc()
        return False

    def _synth_oneshot(self, text, path, timeout):
        try:
            proc = subprocess.run(
                self._base_args() + ["--output_file", path],
                input=(text + "\n").encode("utf-8"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
            )
            return proc.returncode == 0 and self._wait_complete(path)
        except Exception:
            return False

    @staticmethod
    def _wait_complete(path, max_wait=0.3):
        # Piper skriver ut sökvägen strax innan filen stängs: vänta tills WAV:en är hel
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if wav_duration(path) is not None:
                return True
            time.sleep(0.005)
        return False

    def _stop_proc(self):
        if self._proc:
            try:
                self._proc.kill()
                self._proc.wait(timeout=1)
            except Exception:
                pass
        self._proc = None


if __name__ == "__main__":
    import sys
    from phrases import common_phrases

    if "--prewarm" not in sys.argv:
        print("Användning: python3 tts_engine.py --prewarm   (kör UTAN att detect_spatial.py är igång)")
        sys.exit(0)

    engine = TTSEngine()
    phrases = common_phrases()
    todo = engine.missing(phrases)
    print(f"{len(phrases) - len(todo)} av {len(phrases)} fraser finns redan. Genererar {len(todo)}...")
    t0 = time.time()
    for i, text in enumerate(todo, 1):
        engine.synthesize(text, engine.cache_path(text), background=True)
        if i % 20 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}  ({time.time() - t0:.0f} s)")
    left = engine.missing(phrases)
    print("Klart." if not left else f"Klart, men {len(left)} misslyckades.")
