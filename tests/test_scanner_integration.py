# Kör barcode_scanner.main() hela vägen med en låtsaskamera som levererar bilder med en äkta
# streckkod (skapad av zxing-cpp). Kameran (depthai) och OpenCV byts bara ut om de saknas.
import contextlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import timedelta
from unittest import mock

from tests.helpers import EAN_A

try:
    import numpy as np
    import zxingcpp
except ImportError:   # testet kräver numpy och zxing-cpp, som skannern också gör
    np = zxingcpp = None

_INJECTED = []


def setUpModule():
    if np is None:
        raise unittest.SkipTest("numpy och zxing-cpp behövs")
    for name in ("cv2", "depthai"):
        try:
            __import__(name)
        except ImportError:
            sys.modules[name] = types.ModuleType(name)
            _INJECTED.append(name)


def tearDownModule():
    for name in _INJECTED:
        sys.modules.pop(name, None)
    sys.modules.pop("barcode_scanner", None)


class FakeFrame:
    def __init__(self, array):
        self._array = array

    def getCvFrame(self):
        return self._array

    getFrame = getCvFrame

    def getLensPosition(self):
        return 80

    def getExposureTime(self):
        return timedelta(microseconds=30000)

    def getSensitivity(self):
        return 400

    def getSequenceNum(self):
        return 1


class FakeQueue:
    def __init__(self, message, count):
        self._message, self._left = message, count

    def get(self):
        if self._left == 0:
            raise KeyboardInterrupt   # som när Elias trycker Ctrl+C
        self._left -= 1
        return self._message


class FakeDevice:
    def __init__(self, queue):
        self._queue = queue

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def getUsbSpeed(self):
        return types.SimpleNamespace(name="HIGH")

    def getOutputQueue(self, **kwargs):
        return self._queue


class FakeClock:
    """time.time() som går 0,4 s per anrop, så att varje bildruta passerar skannerns egen takt."""

    def __init__(self):
        self._now = 1_800_000_000.0

    def time(self):
        self._now += 0.4
        return self._now

    def strftime(self, *args):
        import time
        return time.strftime(*args)


def barcode_frame(ean, scale=3, center=(960, 540)):
    code = np.array(zxingcpp.create_barcode(ean, zxingcpp.BarcodeFormat.EAN13).to_image(
        scale=scale, add_quiet_zones=True, add_hrt=False))
    canvas = np.full((1080, 1920), 255, np.uint8)
    h, w = code.shape
    y0, x0 = center[1] - h // 2, center[0] - w // 2
    canvas[y0:y0 + h, x0:x0 + w] = code
    return np.ascontiguousarray(np.stack([canvas] * 3, -1))


class ScannerMainTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.karta = os.path.join(self.folder.name, "karta.geojson")
        feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [2.0, 0.69]},
                   "properties": {"ean": EAN_A, "namn": "Tomatpure", "ligger_pa": "sang", "facing": "-x"}}
        with open(self.karta, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": [feature]}, f)

    def run_scanner(self, *flags, frames=6, ean=EAN_A):
        import barcode_scanner
        message = {"color": FakeFrame(barcode_frame(ean)), "depth": FakeFrame(np.full((720, 1280), 300, np.uint16))}
        fake_dai = types.SimpleNamespace(Device=lambda pipeline: FakeDevice(FakeQueue(message, frames)),
                                         UsbSpeed=types.SimpleNamespace(SUPER=1, SUPER_PLUS=2))
        argv = ["barcode_scanner.py", self.karta, "--facit", EAN_A, *flags]
        out, cwd = io.StringIO(), os.getcwd()
        os.chdir(self.folder.name)
        try:
            with mock.patch.object(sys, "argv", argv), mock.patch.object(barcode_scanner, "dai", fake_dai), \
                    mock.patch.object(barcode_scanner, "build_pipeline", return_value=None) as self.build, \
                    mock.patch.object(barcode_scanner, "time", FakeClock()), contextlib.redirect_stdout(out):
                barcode_scanner.main()
        finally:
            os.chdir(cwd)
        return out.getvalue()

    def log_records(self):
        logs = [f for f in os.listdir(os.path.join(self.folder.name, "logs")) if f.endswith(".jsonl")]
        with open(os.path.join(self.folder.name, "logs", logs[0]), encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_without_guidance_flags_nothing_is_spoken(self):
        out = self.run_scanner()
        self.assertNotIn("(confirmed)", out)
        self.assertIn("Facit 7340083497834: 6 rätt, 0 fel", out)
        self.assertEqual(len(self.log_records()), 6)

    def test_text_guidance_confirms_the_product_once(self):
        out = self.run_scanner("--vagledning", "text")
        self.assertEqual(out.count("(confirmed)"), 1)
        self.assertIn("Tomatpure.", out)

    def test_every_log_record_can_be_read_by_the_guidance_engine(self):
        from voice_guidance import CodeRead
        self.run_scanner()
        for rec in self.log_records():
            read = CodeRead.from_record(rec)
            self.assertEqual(read.ean, EAN_A)
            self.assertTrue(read.reliable, rec)
            self.assertAlmostEqual(read.center[0], 0.5, delta=0.02)

    def test_unknown_product_is_announced_as_unknown(self):
        out = self.run_scanner("--vagledning", "text", ean="7311043006847")
        self.assertIn("Okänd vara.", out)

    def test_link_flag_opens_a_port_and_closes_it(self):
        import voice_guidance.session as session_module
        with mock.patch.object(session_module, "_voice_speaker", return_value=session_module.ConsoleSpeaker()):
            out = self.run_scanner("--lank", "0")
        self.assertIn("Länk: 127.0.0.1:", out)

    def test_focus_region_flag_reaches_the_pipeline_and_is_shown(self):
        out = self.run_scanner("--fokusruta")
        self.assertIn("bara rutan i mitten (40 % av bredd och höjd)", out)
        self.build.assert_called_once_with(uhd=False, focus=None, focus_share=0.4)
        self.run_scanner("--fokusruta", "0.25", "--4k")
        self.build.assert_called_once_with(uhd=True, focus=None, focus_share=0.25)

    def test_without_the_flag_autofocus_is_unchanged(self):
        self.run_scanner()
        self.build.assert_called_once_with(uhd=False, focus=None, focus_share=None)

    def test_focus_region_and_locked_focus_cannot_be_combined(self):
        for flags in (("--fokusruta", "--fokus", "70"), ("--fokusruta", "0.05"), ("--fokusruta", "1.5")):
            with self.subTest(flags=flags), self.assertRaises(SystemExit):
                self.run_scanner(*flags)

    def test_focus_region_is_centred(self):
        import barcode_scanner
        self.assertEqual(barcode_scanner.focus_region(1920, 1080, 0.4), (576, 324, 768, 432))
        self.assertEqual(barcode_scanner.focus_region(3840, 2160, 1.0), (0, 0, 3840, 2160))
        with self.assertRaises(ValueError):
            barcode_scanner.focus_region(1920, 1080, 0)

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_scanner("--lank", "70000")


if __name__ == "__main__":
    unittest.main()
