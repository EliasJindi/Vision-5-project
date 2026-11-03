import contextlib
import io
import json
import os
import tempfile
import unittest

from voice_guidance import ActionKind, DictProductCatalog, GuidanceEngine
from voice_guidance.replay import frames_from_records, main, replay

from tests.helpers import EAN_A, EAN_B, THIN_CORNERS, record

CATALOG = DictProductCatalog({EAN_A: [{"namn": "Tomatpure"}]})


class FramesTest(unittest.TestCase):
    def test_records_with_the_same_timestamp_are_one_frame(self):
        records = [record(1.0), record(1.0, ean=EAN_B), record(2.0), record(3.0)]
        frames = list(frames_from_records(records))
        self.assertEqual([(t, len(recs)) for t, recs in frames], [(1.0, 2), (2.0, 1), (3.0, 1)])

    def test_no_records_no_frames(self):
        self.assertEqual(list(frames_from_records([])), [])


class ReplayTest(unittest.TestCase):
    def test_correct_confirmation_is_marked_correct(self):
        records = [record(1.0, facit=EAN_A, filter=[]), record(1.5, facit=EAN_A, filter=[])]
        report = replay(records, GuidanceEngine(CATALOG), "ok")
        self.assertEqual([e.action.kind for e in report.events], [ActionKind.CONFIRMED])
        self.assertTrue(report.events[0].correct)
        self.assertEqual(report.wrong_confirmations, [])

    def test_wrong_confirmation_is_counted(self):
        records = [record(1.0, ean=EAN_B, facit=EAN_A, filter=[]), record(1.5, ean=EAN_B, facit=EAN_A, filter=[])]
        report = replay(records, GuidanceEngine(CATALOG), "fel")
        self.assertEqual(len(report.wrong_confirmations), 1)
        self.assertEqual(report.wrong_confirmations[0].action.kind, ActionKind.UNKNOWN_PRODUCT)

    def test_thin_misreads_alone_never_produce_a_confirmation(self):
        records = [record(1.0 + i * 0.5, ean=EAN_B, corners=THIN_CORNERS, facit=EAN_A) for i in range(10)]
        report = replay(records, GuidanceEngine(CATALOG), "tunna")
        self.assertEqual(report.confirmations, [])
        self.assertGreaterEqual(report.count(ActionKind.CLOSER), 1)

    def test_without_facit_correctness_is_unknown(self):
        records = [record(1.0, filter=[]), record(1.5, filter=[])]
        self.assertIsNone(replay(records, GuidanceEngine(CATALOG)).events[0].correct)

    def test_unreadable_records_are_skipped(self):
        records = [{"t": 1.0, "ean": EAN_A}, record(2.0, filter=[]), record(2.5, filter=[])]
        report = replay(records, GuidanceEngine(CATALOG))
        self.assertEqual(report.frames, 3)
        self.assertEqual(len(report.confirmations), 1)


class CommandLineTest(unittest.TestCase):
    def run_main(self, records, extra=()):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "scan_test.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")
                f.write("\x00trasig sista rad\n")   # som efter ett strömavbrott
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([path, *extra])
            return code, out.getvalue()

    def test_clean_log_exits_zero_and_prints_a_summary(self):
        code, out = self.run_main([record(1.0, facit=EAN_A, filter=[]), record(1.5, facit=EAN_A, filter=[])])
        self.assertEqual(code, 0)
        self.assertIn("Totalt: 1 loggar", out)
        self.assertIn("0 fel vara", out)

    def test_wrong_product_announcement_exits_nonzero(self):
        code, out = self.run_main([record(1.0, ean=EAN_B, facit=EAN_A, filter=[]),
                                   record(1.5, ean=EAN_B, facit=EAN_A, filter=[])])
        self.assertEqual(code, 1)
        self.assertIn("FEL VARA", out)

    def test_hand_convention_changes_the_words(self):
        thin_left = record(1.0, corners=[[100, 500], [300, 500], [300, 501], [100, 501]], filter=["tunn"])
        _, head = self.run_main([thin_left], ["--sikte", "huvud"])
        _, hand = self.run_main([thin_left], ["--sikte", "hand"])
        self.assertIn("Lite åt vänster.", head)
        self.assertIn("Lite åt höger.", hand)


if __name__ == "__main__":
    unittest.main()
