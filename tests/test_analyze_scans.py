import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import analyze_scans
from tests.helpers import EAN_A, FULL_CORNERS, THIN_CORNERS, record


def rec(px, thin=False, ean=EAN_A, mode="4k", filter_field=True):
    r = record(1.0, ean=ean, corners=THIN_CORNERS if thin else FULL_CORNERS,
               filter=(["tunn"] if thin else []) if filter_field else None)
    r["px_per_modul"] = px
    r["mode"] = mode
    return r


class PixelSamplesTest(unittest.TestCase):
    def test_reliable_means_the_same_as_for_the_voice(self):
        samples = analyze_scans.pixel_samples({"a_4k.jsonl": [
            rec(3.0), rec(2.7, thin=True), rec(2.0, ean=None),
            rec(2.5, thin=True, filter_field=False),          # äldre logg: tunn räknas ur hörnen
        ]})
        self.assertEqual([ok for _, ok, _ in samples["4k"]], [True, False, False, False])

    def test_rows_without_pixels_or_corners_are_skipped(self):
        broken = rec(2.0)
        del broken["hornen"]
        samples = analyze_scans.pixel_samples({"a_4k.jsonl": [broken, {**rec(2.0), "px_per_modul": None}, rec(2.2)]})
        self.assertEqual(len(samples["4k"]), 1)

    def test_mode_comes_from_the_file_name_when_the_row_lacks_it(self):
        r = rec(2.0)
        del r["mode"]
        self.assertIn("1080p", analyze_scans.pixel_samples({"scan_20261020_101010_1080p.jsonl": [r]}))

    def test_buckets_have_closed_lower_edges(self):
        self.assertEqual(analyze_scans.bucket_of(1.49), 0)
        self.assertEqual(analyze_scans.bucket_of(1.5), 1)
        self.assertEqual(analyze_scans.bucket_of(3.5), len(analyze_scans.PX_EDGES))


class PixelReportTest(unittest.TestCase):
    def report(self, logs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            analyze_scans.pixel_report(logs)
        return out.getvalue()

    def test_the_hold_still_rule_is_counted_per_threshold(self):
        out = self.report({"a_4k.jsonl": [rec(2.6), rec(3.1), rec(2.7, thin=True)],
                           "b_4k.jsonl": [rec(1.6, thin=True)]})
        self.assertIn("4k: 2 säkra, 2 osäkra, från 2 körningar", out)
        self.assertIn('T = 2,50: 1 av 2 osäkra skulle få "håll stilla"; vid minst T: 67% av läsningarna var säkra (3 st)', out)
        self.assertIn('T = 3,00: 0 av 2 osäkra', out)
        self.assertIn("Säkra: median 2,85 px/modul", out)   # medel av 2,6 och 3,1 vid jämnt antal
        self.assertIn("Osäkra: median 2,15 px/modul (10–90 %: 1,60–2,70)", out)

    def test_empty_logs_say_so(self):
        self.assertIn("Inga läsningar", self.report({"a_4k.jsonl": []}))


class CommandLineTest(unittest.TestCase):
    def run_main(self, *flags):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "scan_20261106_115346_4k.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for r in (rec(3.0), rec(2.7, thin=True)):
                    f.write(json.dumps(r) + "\n")
            out = io.StringIO()
            with mock.patch("sys.argv", ["analyze_scans.py", path, *flags]), contextlib.redirect_stdout(out):
                analyze_scans.main()
        return out.getvalue()

    def test_the_default_output_is_unchanged(self):
        out = self.run_main()
        self.assertIn("Orimligt djup", out)
        self.assertNotIn("Säkra och osäkra", out)

    def test_the_flag_prints_only_the_pixel_report(self):
        out = self.run_main("--pixlar")
        self.assertIn("Säkra och osäkra", out)
        self.assertNotIn("Orimligt djup", out)


def lens_rec(d, lens, thin=False, correct=None, filt=None):
    r = rec(3.0, thin=thin)
    r.update(distance_m=d, lins=lens)
    if correct is not None:
        r["correct"] = correct
    if filt is not None:
        r["filter"] = filt
    return r


class LensTest(unittest.TestCase):
    def test_only_reliable_correct_reads_with_plausible_depth_count(self):
        samples = analyze_scans.lens_samples({"a_4k.jsonl": [
            lens_rec(0.35, 80), lens_rec(0.35, 20, thin=True), lens_rec(0.35, 20, correct=False),
            lens_rec(3.0, 20), lens_rec(0.35, 20, filt=["orimligt djup"]), {**lens_rec(0.35, 20), "lins": None}]})
        self.assertEqual([(d, lens) for d, lens, _ in samples], [(0.35, 80)])

    def test_the_fit_recovers_a_lens_that_follows_one_over_distance(self):
        samples = [(d, round(20 + 20 / d), "a") for d in (0.25, 0.3, 0.35, 0.4, 0.5)]
        a, b, err = analyze_scans.fit_lens(samples)
        self.assertAlmostEqual(a, 20, delta=1.5)
        self.assertAlmostEqual(b, 20, delta=0.5)
        self.assertLess(err, 1)

    def test_too_few_distances_give_no_fit(self):
        self.assertIsNone(analyze_scans.fit_lens([(0.3, 80, "a"), (0.3, 81, "a"), (0.4, 75, "a")]))

    def test_the_report_groups_by_distance(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            analyze_scans.lens_report({"a_4k.jsonl": [lens_rec(0.32, 80), lens_rec(0.33, 84), lens_rec(0.45, 70)],
                                       "b_4k.jsonl": [lens_rec(0.26, 90)]})
        text = out.getvalue()
        self.assertIn("4 läsningar från 2 körningar", text)
        self.assertIn("0,30-0,35", text)
        self.assertIn("Anpassning: lins =", text)


if __name__ == "__main__":
    unittest.main()
