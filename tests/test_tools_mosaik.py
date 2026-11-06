import unittest

from tools.mosaik import hhmmss, latest_run, narrow, pick_even

RUN = [f"logs/snapshots/snap_{i:03d}_1211{30 + 2 * i:02d}.jpg" for i in range(1, 15)]   # 12:11:32 ... 12:11:58


class LatestRunTest(unittest.TestCase):
    def test_only_the_newest_run_is_taken(self):
        old = ["logs/snapshots/snap_001_090000.jpg", "logs/snapshots/snap_002_090002.jpg"]
        times = {f: 1000 + 2 * i for i, f in enumerate(RUN)}
        times.update({old[0]: 100, old[1]: 102})                          # en timme tidigare
        self.assertEqual(latest_run(old + RUN, mtime=times.get), RUN)

    def test_a_gap_over_twenty_seconds_starts_a_new_run(self):
        times = {RUN[0]: 0, RUN[1]: 2, RUN[2]: 40, RUN[3]: 42}
        self.assertEqual(latest_run(RUN[:4], mtime=times.get), RUN[2:4])

    def test_no_files_gives_an_empty_run(self):
        self.assertEqual(latest_run([]), [])


class NarrowTest(unittest.TestCase):
    def test_time_from_the_file_name(self):
        self.assertEqual(hhmmss("logs/snapshots/snap_011_121233.jpg"), "121233")

    def test_middle_is_the_middle_half(self):
        self.assertEqual(narrow(RUN, ["mitten"]), RUN[3:11])

    def test_a_time_window_keeps_the_ends(self):
        picked = narrow(RUN, ["12:11:40", "12:11:46"])
        self.assertEqual([hhmmss(f) for f in picked], ["121140", "121142", "121144", "121146"])

    def test_no_extra_arguments_keep_everything_and_bad_ones_are_refused(self):
        self.assertEqual(narrow(RUN, []), RUN)
        with self.assertRaises(ValueError):
            narrow(RUN, ["fel"])


class PickEvenTest(unittest.TestCase):
    def test_first_and_last_are_always_included(self):
        picked = pick_even(list(range(56)))
        self.assertEqual((len(picked), picked[0], picked[-1]), (16, 0, 55))

    def test_short_runs_are_taken_whole(self):
        self.assertEqual(pick_even([1, 2, 3]), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
