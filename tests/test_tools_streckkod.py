import unittest

from tools.streckkod import quads, summarize


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


class SummarizeTest(unittest.TestCase):
    def test_counts_only_frames_with_a_hand(self):
        rows = [(True, True, True), (True, True, False), (True, False, True), (True, False, False),
                (False, True, True)]
        self.assertEqual(summarize(rows), {"bilder": 5, "med_hand": 4, "upptackt": 2, "last": 2,
                                           "upptackt_ej_last": 1, "last_ej_upptackt": 1})


if __name__ == "__main__":
    unittest.main()
