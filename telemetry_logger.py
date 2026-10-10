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
    def __init__(self, log_dir="logs", flush_interval=1.0):
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, f"session_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
        self._q = queue.Queue(maxsize=10000)
        self._ids = itertools.count(1)
        self._flush_interval = flush_interval
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

    def start_vitals(self, qsize_fn=None, interval=5.0):
        """Loggar temperatur, throttling-status och ljudköns längd var 'interval' sekund."""
        def loop():
            while not self._stop.is_set():
                self.log(
                    "vitals",
                    temp_c=self._read_temp(),
                    throttled=self._read_throttled(),
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
            last_flush = time.time()
            while not self._stop.is_set() or not self._q.empty():
                try:
                    rec = self._q.get(timeout=0.5)
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                except queue.Empty:
                    pass
                if time.time() - last_flush >= self._flush_interval:
                    f.flush()
                    last_flush = time.time()
            f.flush()

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


# Global instans, på samma sätt som audio_system
telemetry = TelemetryLogger()
