import unittest

from tools.streckkod import pick_tiles, quads, summarize


class QuadsTest(unittest.TestCase):
    def test_nothing_found(self):
        self.assertEqual(quads((False, None)), [])
        self.assertEqual(quads((True, None)), [])

    def test_points_are_moved_back_to_the_whole_image(self):
        found = quads((True, [[(10, 20), (110, 20), (110, 60), (10, 60)]]), dx=1000, dy=500)
        self.assertEqual(found, [[(1010.0, 520.0), (1110.0, 520.0), (1110.0, 560.0), (1010.0, 560.0)]])

    def test_a_downscaled_crop_is_scaled_back_up(self):
        found = quads((True, [[(10, 20), (110, 20), (110, 60), (10, 60)]]), dx=100, dy=0, scale=0.5)
        self.assertEqual(found[0][1], (320.0, 40.0))


class PickTilesTest(unittest.TestCase):
    def test_every_hit_is_included_and_the_rest_is_spread_out(self):
        flags = [False] * 45
        for i in (17, 19, 21, 33):
            flags[i] = True
        picked = pick_tiles(flags)
        self.assertEqual(len(picked), 16)
        self.assertTrue({17, 19, 21, 33} <= set(picked))
        self.assertEqual(picked, sorted(picked))                          # tidsordning
        self.assertIn(0, picked)
        self.assertIn(44, picked)

    def test_more_hits_than_room_keeps_the_first(self):
        self.assertEqual(pick_tiles([True] * 20, n=16), list(range(16)))

    def test_short_runs_are_taken_whole(self):
        self.assertEqual(pick_tiles([False, True, False]), [0, 1, 2])
        self.assertEqual(pick_tiles([]), [])


class SummarizeTest(unittest.TestCase):
    def test_counts_only_frames_with_a_hand(self):
        rows = [(True, True, True), (True, True, False), (True, False, True), (True, False, False),
                (False, True, True)]
        self.assertEqual(summarize(rows), {"bilder": 5, "med_hand": 4, "upptackt": 2, "last": 2,
                                           "upptackt_ej_last": 1, "last_ej_upptackt": 1})


if __name__ == "__main__":
    unittest.main()
