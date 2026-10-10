"""
telemetry_logger.py - Tyst telemetri för Vision-5.

Principer:
  * Huvudloopen får ALDRIG blockeras: log() lägger bara en post i en kö.
  * En egen skrivtråd buffrar och flushar till disk (JSONL, en händelse per rad).
  * Hög-frekventa händelser (filterbeslut som blockeras) loggas INTE per bildruta,
    utan räknas och sammanfattas var 5:e sekund (se filter_summary).
"""
import itertools
import json
import os
import queue
import subprocess
import threading
import time


class TelemetryLogger:
    def __init__(self, log_dir="logs", flush_interval=1.0, fsync_interval=2.0):
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, f"session_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
        self._q = queue.Queue(maxsize=10000)
        self._ids = itertools.count(1)
        self._flush_interval = flush_interval
        # flush() lämnar bara datan till Linux; vid strömavbrott försvinner de senaste ~5 s.
        # fsync() tvingar ut den till SD-kortet, så att vi ser vad som hände precis före en krasch.
        self._fsync_interval = fsync_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()

    # ---------- publikt API ----------
    def new_id(self):
        """Unikt meddelande-id, används för att följa ett meddelande genom hela kedjan."""
        return next(self._ids)

    def log(self, event, **fields):
        """Icke-blockerande. Om kön skulle bli full kastas posten hellre än att huvudloopen hänger."""
        rec = {"t": round(time.time(), 3), "event": event}
        rec.update(fields)
        try:
            self._q.put_nowait(rec)
        except queue.Full:
            pass

    def start_vitals(self, qsize_fn=None, interval=1.0):
        """Loggar temperatur, spänning, throttling-status och ljudköns längd var 'interval' sekund."""
        def loop():
            while not self._stop.is_set():
                throttled = self._read_throttled()
                self.log(
                    "vitals",
                    temp_c=self._read_temp(),
                    voltage_v=self._read_voltage(),
                    throttled=throttled,
                    # Bit 0 = underspänning JUST NU (bit 16 är "har hänt sedan boot" och säger inget om när)
                    undervolt_now=self._bit(throttled, 0),
                    audio_qsize=qsize_fn() if qsize_fn else None,
                )
                self._stop.wait(interval)

        threading.Thread(target=loop, daemon=True).start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)

    # ---------- internt ----------
    def _writer(self):
        with open(self.path, "a", encoding="utf-8") as f:
            last_flush = last_fsync = time.time()
            while not self._stop.is_set() or not self._q.empty():
                try:
                    rec = self._q.get(timeout=0.5)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except queue.Empty:
                    pass
                now = time.time()
                if now - last_flush >= self._flush_interval:
                    f.flush()
                    last_flush = now
                if now - last_fsync >= self._fsync_interval:
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
                    last_fsync = now
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _read_temp():
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return None

    @staticmethod
    def _read_throttled():
        try:
            out = subprocess.run(
                ["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=1
            ).stdout.strip()
            return out.split("=")[-1]  # t.ex. '0x0'
        except Exception:
            return None

    @staticmethod
    def _bit(hex_str, bit):
        try:
            return bool(int(hex_str, 16) & (1 << bit))
        except Exception:
            return None

    @staticmethod
    def _read_voltage():
        """EXT5V_V från PMIC = spänningen in i Pi:n. Under ca 4,63 V varnar Pi:n för underspänning."""
        try:
            out = subprocess.run(
                ["vcgencmd", "pmic_read_adc", "EXT5V_V"], capture_output=True, text=True, timeout=1
            ).stdout
            for line in out.splitlines():
                if "EXT5V_V" in line:
                    return round(float(line.split("=")[-1].strip().rstrip("V")), 3)
        except Exception:
            pass
        return None


# Global instans, på samma sätt som audio_system
telemetry = TelemetryLogger()
