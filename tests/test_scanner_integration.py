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

    def getInputQueue(self, name):
        self.control = ControlRecorder()
        FakeDevice.last = self
        return self.control


class ControlRecorder:
    """Kontrollkanalen till kameran (--hand): sparar det som skickas."""

    def __init__(self):
        self.sent = []

    def send(self, ctrl):
        self.sent.append(ctrl)


class FakeCameraControl:
    AutoFocusMode = types.SimpleNamespace(CONTINUOUS_VIDEO="continuous_video")

    def __init__(self):
        self.calls = []

    def setManualFocus(self, lens):
        self.calls.append(("lens", lens))

    def setAutoFocusMode(self, mode):
        self.calls.append(("autofocus", mode))

    def setAutoExposureRegion(self, *args):
        self.calls.append(("exposure", args))


class FakeClock:
    """time.time() som går 0,4 s per anrop, så att varje bildruta passerar skannerns egen takt."""

    def __init__(self):
        self._now = 1_800_000_000.0

    def time(self):
        self._now += 0.4
        return self._now

    def perf_counter(self):
        import time
        return time.perf_counter()

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

    def run_scanner(self, *flags, frames=6, ean=EAN_A, depth=None, center=(960, 540)):
        import barcode_scanner
        depth = np.full((720, 1280), 300, np.uint16) if depth is None else depth
        message = {"color": FakeFrame(barcode_frame(ean, center=center)), "depth": FakeFrame(depth)}
        fake_dai = types.SimpleNamespace(Device=lambda pipeline: FakeDevice(FakeQueue(message, frames)),
                                         UsbSpeed=types.SimpleNamespace(SUPER=1, SUPER_PLUS=2),
                                         CameraControl=FakeCameraControl)
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
        self.build.assert_called_once_with(uhd=False, focus=None, focus_share=0.4, hand=False)
        self.run_scanner("--fokusruta", "0.25", "--4k")
        self.build.assert_called_once_with(uhd=True, focus=None, focus_share=0.25, hand=False)

    def test_hand_mode_is_the_default_and_can_be_turned_off(self):
        out = self.run_scanner()
        self.build.assert_called_once_with(uhd=False, focus=None, focus_share=None, hand=True)
        self.assertIn("Fokus: efter handens avstånd", out)
        out = self.run_scanner("--utan-hand")
        self.build.assert_called_once_with(uhd=False, focus=None, focus_share=None, hand=False)
        self.assertIn("Fokus: autofokus", out)
        self.assertNotIn("Hand: hittad", out)

    def test_manual_focus_turns_hand_mode_off_without_complaint(self):
        self.run_scanner("--fokus", "70")
        self.build.assert_called_once_with(uhd=False, focus=70, focus_share=None, hand=False)

    def test_hand_and_without_hand_together_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_scanner("--hand", "--utan-hand")

    def test_diag_pictures_go_to_a_folder_per_run(self):
        import barcode_scanner
        with mock.patch.object(barcode_scanner, "diagnose", return_value="📷 test") as diag:
            self.run_scanner("--diag")
        folder = diag.call_args[0][3]
        self.assertTrue(folder.startswith(os.path.join("logs", "snapshots", "scan_")), folder)
        self.assertTrue(folder.endswith("_1080p"), folder)

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

    def test_hand_mode_reads_the_code_in_the_hand_with_the_same_corners(self):
        self.run_scanner(center=(1300, 800))
        plain = self.log_records()
        os.remove(os.path.join(self.folder.name, "logs", [f for f in os.listdir(os.path.join(self.folder.name, "logs"))
                                                          if f.endswith(".jsonl")][0]))
        depth = np.full((720, 1280), 1500, np.uint16)
        depth[400:720, 700:1100] = 350                                    # handen nere till höger, som 6/11
        out = self.run_scanner("--hand", center=(1300, 800), depth=depth)
        hand = self.log_records()
        self.assertIn("Fokus: efter handens avstånd, ljuset efter handen", out)
        self.assertEqual({r["avkodat_i"] for r in hand}, {"ruta"})
        # Samma koordinater som utan handruta. zxing kan hamna 1 px annorlunda i en beskuren bild, inte mer.
        for got, want in zip(hand, plain):
            for (gx, gy), (wx, wy) in zip(got["hornen"], want["hornen"]):
                self.assertLessEqual(max(abs(gx - wx), abs(gy - wy)), 1, (got["hornen"], want["hornen"]))
        self.assertEqual(len(hand), len(plain))
        self.assertAlmostEqual(hand[0]["hand_m"], 0.35, delta=0.01)
        self.assertIn("koden hittad i handrutan 6 gånger", out)
        sent = FakeDevice.last.control.sent
        self.assertEqual(len(sent), 1)                                    # handen står still: en gång räcker
        from hand_region import lens_for_distance
        self.assertEqual(sent[0].calls[0], ("lens", lens_for_distance(hand[0]["hand_m"])))   # linsen efter avståndet
        self.assertEqual(sent[0].calls[1][0], "exposure")
        x, y, w, h = sent[0].calls[1][1]
        self.assertTrue(x >= 1000 and y >= 500, (x, y))                   # ljuset efter handen nere till höger

    def test_a_code_outside_the_hand_is_still_found(self):
        depth = np.full((720, 1280), 1500, np.uint16)
        depth[0:200, 0:300] = 350                                         # "handen" uppe till vänster, koden i mitten
        self.run_scanner("--hand", depth=depth)
        self.assertEqual({r["avkodat_i"] for r in self.log_records()}, {"hela"})

    def test_without_a_hand_nothing_is_sent_and_the_whole_image_is_read(self):
        out = self.run_scanner("--hand", depth=np.full((720, 1280), 1500, np.uint16))
        self.assertEqual(FakeDevice.last.control.sent, [])
        self.assertEqual({r["avkodat_i"] for r in self.log_records()}, {"hela"})
        self.assertIn("Hand: hittad i 0 av", out)

    def test_when_the_hand_goes_away_autofocus_comes_back(self):
        import barcode_scanner
        sent = []

        class Queue:
            def send(self, ctrl):
                sent.append(ctrl)

        hand = barcode_scanner.HandFocus()
        region = barcode_scanner.find_near_region(np.pad(np.full((320, 400), 350, np.uint16), ((400, 0), (700, 180)),
                                                         constant_values=1500))
        fake_dai = types.SimpleNamespace(CameraControl=FakeCameraControl)
        with mock.patch.object(barcode_scanner, "dai", fake_dai):
            for t, r in ((0.0, region), (0.5, None), (2.0, None)):
                command = hand.update(t, r)
                if command is not None:
                    barcode_scanner.send_focus(Queue(), command, 1920, 1080)
        self.assertEqual([c.calls[0][0] for c in sent], ["lens", "autofocus"])
        self.assertEqual(sent[1].calls[1], ("exposure", (0, 0, 1920, 1080)))   # ljuset över hela bilden igen

    def test_hand_mode_cannot_be_combined_with_other_focus_flags(self):
        for flags in (("--hand", "--fokus", "70"), ("--hand", "--fokusruta")):
            with self.subTest(flags=flags), self.assertRaises(SystemExit):
                self.run_scanner(*flags)

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_scanner("--lank", "70000")


if __name__ == "__main__":
    unittest.main()
