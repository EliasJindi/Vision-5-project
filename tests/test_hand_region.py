import unittest

import numpy as np

from hand_region import NearRegion, cell_medians, find_near_region

H, W = 720, 1280


def scene(background=1500):
    return np.full((H, W), background, np.uint16)


def put(depth, x0, y0, x1, y1, mm):
    depth[y0:y1, x0:x1] = mm
    return depth


class FindNearRegionTest(unittest.TestCase):
    def test_a_hand_low_in_the_image_is_found_with_its_distance(self):
        region = find_near_region(put(scene(), 500, 500, 800, 700, 350))   # som i mosaikerna 6/11
        self.assertAlmostEqual(region.x0, 500 / W, delta=0.02)
        self.assertAlmostEqual(region.x1, 800 / W, delta=0.02)
        self.assertAlmostEqual(region.y0, 500 / H, delta=0.03)
        self.assertAlmostEqual(region.y1, 700 / H, delta=0.03)
        self.assertAlmostEqual(region.depth_m, 0.35, delta=0.01)
        self.assertGreater(region.center[1], 0.6)                          # i nedre delen av bilden

    def test_nothing_within_arms_length_gives_none(self):
        self.assertIsNone(find_near_region(scene()))
        self.assertIsNone(find_near_region(np.zeros((H, W), np.uint16)))   # inget djup alls

    def test_holes_in_the_depth_do_not_hide_the_hand(self):
        depth = put(scene(), 500, 500, 800, 700, 350)
        depth[500:700:3, 500:800] = 0                                      # var tredje rad saknar djup
        self.assertIsNotNone(find_near_region(depth))

    def test_a_single_noisy_speck_is_ignored(self):
        self.assertIsNone(find_near_region(put(scene(), 100, 100, 120, 120, 300)))

    def test_a_table_edge_further_away_is_not_part_of_the_hand(self):
        depth = put(scene(), 0, 650, W, H, 600)                            # bordskant 60 cm, hela bredden
        depth = put(depth, 500, 400, 800, 640, 350)                        # handen 35 cm
        region = find_near_region(depth)
        self.assertAlmostEqual(region.x0, 500 / W, delta=0.02)
        self.assertAlmostEqual(region.x1, 800 / W, delta=0.02)
        self.assertLess(region.y1, 650 / H + 0.03)

    def test_the_largest_surface_in_the_nearest_layer_wins(self):
        depth = put(scene(), 100, 100, 200, 200, 380)                      # liten sak, 38 cm
        depth = put(depth, 600, 300, 900, 600, 400)                        # handen, 40 cm, mycket större
        self.assertGreater(find_near_region(depth).x0, 0.4)

    def test_an_angled_shape_is_found_whole(self):
        # Varan uppe till höger, handen och armen nedanför och åt vänster: sökningen måste gå åt alla håll.
        depth = put(scene(), 700, 300, 800, 400, 350)
        depth = put(depth, 400, 400, 800, 500, 360)
        region = find_near_region(depth)
        self.assertAlmostEqual(region.x0, 400 / W, delta=0.02)
        self.assertAlmostEqual(region.y0, 300 / H, delta=0.03)

    def test_outside_the_distance_window_is_ignored(self):
        self.assertIsNone(find_near_region(put(scene(), 500, 500, 800, 700, 150)))   # för nära för djup
        self.assertIsNone(find_near_region(put(scene(), 500, 500, 800, 700, 900)))   # bortom en armlängd


class HelpersTest(unittest.TestCase):
    def test_cell_medians_ignore_missing_depth(self):
        depth = np.full((40, 40), 500, np.uint16)
        depth[:20, :20] = 0
        med = cell_medians(depth, 20)
        self.assertTrue(np.isnan(med[0, 0]))
        self.assertEqual(med[1, 1], 500)

    def test_too_small_image_is_an_error(self):
        with self.assertRaises(ValueError):
            cell_medians(np.zeros((10, 10), np.uint16), 20)

    def test_region_to_pixels(self):
        region = NearRegion(0.25, 0.5, 0.75, 1.0, 0.4, 0.1)
        self.assertEqual(region.to_pixels(3840, 2160), (960, 1080, 1920, 1080))
        self.assertEqual(region.center, (0.5, 0.75))


if __name__ == "__main__":
    unittest.main()
