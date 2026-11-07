import unittest

from tools.streckkod import pick_tiles, quads, summarize, zoom_box


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
        rows = [(True, True, True, False), (True, True, False, True), (True, False, True, False),
                (True, False, False, False), (False, True, True, False), (True, True, False, False)]
        self.assertEqual(summarize(rows), {"bilder": 6, "med_hand": 5, "upptackt": 3, "last": 2,
                                           "upptackt_ej_last": 2, "last_ej_upptackt": 1, "raddade": 1})


class ZoomBoxTest(unittest.TestCase):
    def test_margin_follows_the_longest_side_and_stays_inside(self):
        quad = [(100, 200), (300, 200), (300, 240), (100, 240)]          # 200 bred, 40 hög
        self.assertEqual(zoom_box(quad, 1920, 1080), (40, 140, 361, 301))   # 30 % av 200 = 60 åt alla håll
        self.assertEqual(zoom_box([(5, 5), (50, 5), (50, 20), (5, 20)], 1920, 1080)[:2], (0, 0))
        self.assertEqual(zoom_box([(1900, 1070), (1919, 1070), (1919, 1079), (1900, 1079)], 1920, 1080)[2:], (1920, 1080))


if __name__ == "__main__":
    unittest.main()
