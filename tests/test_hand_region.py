import unittest

import numpy as np

from hand_region import LENS_TABLE, FocusCommand, HandFocus, NearRegion, cell_medians, find_near_region, lens_for_distance

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


def box(x0, y0, x1, y1):
    return NearRegion(x0, y0, x1, y1, 0.35, (x1 - x0) * (y1 - y0))


class ExpandedTest(unittest.TestCase):
    def test_margin_is_added_but_kept_inside_the_image(self):
        r = box(0.05, 0.5, 0.6, 0.95).expanded(0.1)
        self.assertEqual(tuple(round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)), (0.0, 0.4, 0.7, 1.0))


class HandFocusTest(unittest.TestCase):
    def setUp(self):
        self.focus = HandFocus()
        self.hand = box(0.45, 0.45, 0.9, 0.95)

    def test_the_first_hand_is_sent_at_once(self):
        self.assertEqual(self.focus.update(0.0, self.hand), FocusCommand(self.hand))

    def test_a_still_hand_is_not_sent_again(self):
        self.focus.update(0.0, self.hand)
        for t in (0.5, 1.0, 1.5):
            self.assertIsNone(self.focus.update(t, box(0.46, 0.45, 0.91, 0.95)), t)   # 1 % flytt: brus

    def test_a_moved_hand_is_sent_but_not_more_often_than_twice_a_second(self):
        self.focus.update(0.0, self.hand)
        moved = box(0.2, 0.45, 0.65, 0.95)
        self.assertIsNone(self.focus.update(0.3, moved))                    # för tätt
        self.assertEqual(self.focus.update(0.6, moved), FocusCommand(moved))

    def test_a_hand_that_comes_closer_counts_as_moved_so_the_lens_follows(self):
        self.focus.update(0.0, self.hand)
        closer = NearRegion(0.45, 0.45, 0.9, 0.95, 0.30, 0.2)            # samma ruta, 5 cm närmare
        self.assertEqual(self.focus.update(1.0, closer).region, closer)
        self.assertIsNone(self.focus.update(2.0, NearRegion(0.45, 0.45, 0.9, 0.95, 0.31, 0.2)))   # 1 cm: brus

    def test_a_hand_that_grows_counts_as_moved(self):
        self.focus.update(0.0, self.hand)
        closer = box(0.4, 0.35, 0.95, 1.0)                                  # samma mitt, större
        self.assertEqual(self.focus.update(1.0, closer).region, closer)

    def test_focus_returns_to_the_whole_image_when_the_hand_is_gone(self):
        self.focus.update(0.0, self.hand)
        self.assertIsNone(self.focus.update(0.5, None))                     # kort tapp: behåll
        self.assertEqual(self.focus.update(1.5, None), FocusCommand(None))
        self.assertIsNone(self.focus.update(2.0, None))                     # bara en gång

    def test_crop_is_the_hand_with_margin_until_it_is_lost(self):
        self.focus.update(0.0, self.hand)
        crop = self.focus.crop(0.5)
        self.assertAlmostEqual(crop.x0, 0.35)
        self.assertAlmostEqual(crop.y1, 1.0)
        self.assertIsNone(self.focus.crop(1.5))
        self.assertIsNone(HandFocus().crop(0.0))


class LensForDistanceTest(unittest.TestCase):
    def test_the_table_points_are_hit_exactly(self):
        for distance, lens in LENS_TABLE:
            self.assertEqual(lens_for_distance(distance), lens, distance)

    def test_between_points_it_interpolates(self):
        self.assertEqual(lens_for_distance(0.25), 79)                      # mitt emellan 82 och 76
        self.assertEqual(lens_for_distance(0.375), 75)                     # mitt emellan 76 och 74

    def test_outside_the_table_it_holds_the_ends(self):
        self.assertEqual(lens_for_distance(0.10), 82)
        self.assertEqual(lens_for_distance(2.0), 66)

    def test_every_value_lies_where_reads_have_succeeded(self):
        # analyze_scans --lins 7/11: alla säkra läsningar vid linsläge 66-92
        for cm in range(15, 100):
            self.assertTrue(66 <= lens_for_distance(cm / 100) <= 92, cm)


if __name__ == "__main__":
    unittest.main()
