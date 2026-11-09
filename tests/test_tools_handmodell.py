import unittest

import numpy as np

from hand_region import NearRegion
from hand_model import (Palm, decode_palms, hand_rect, iou, letterbox_rows, non_max_suppression, overlaps,
                        palm_anchors, shrink_factor, square_to_frame)
from tools.handmodell import (above_text, confirmed_within, crop_to_frame, median_text, mosaic_path, share_text,
                              square_crop, summarize)


def logit(p):
    return float(np.log(p / (1 - p)))


class AnchorTest(unittest.TestCase):
    def test_same_count_and_order_as_the_model(self):
        a = palm_anchors()
        self.assertEqual(a.shape, (896, 2))                              # modellens 896 rutor
        np.testing.assert_allclose(a[0], a[1])                           # två per cell i första lagret
        np.testing.assert_allclose(a[0], (0.5 / 16, 0.5 / 16))
        np.testing.assert_allclose(a[2], (1.5 / 16, 0.5 / 16))           # nästa cell åt höger
        np.testing.assert_allclose(a[32], (0.5 / 16, 1.5 / 16))          # nästa rad: 16 celler x 2
        np.testing.assert_allclose(a[512], (0.5 / 8, 0.5 / 8))           # 8x8-lagret börjar
        np.testing.assert_allclose(a[512:518], [(0.5 / 8, 0.5 / 8)] * 6)   # sex per cell
        np.testing.assert_allclose(a[518], (1.5 / 8, 0.5 / 8))
        np.testing.assert_allclose(a[-1], (7.5 / 8, 7.5 / 8))


class DecodeTest(unittest.TestCase):
    def setUp(self):
        self.anchors = palm_anchors()
        self.scores = np.full(896, -10.0)
        self.reg = np.zeros((896, 18))

    def test_a_confident_box_is_placed_relative_to_its_anchor(self):
        self.scores[600] = logit(0.9)
        self.reg[600, :4] = (12.8, -6.4, 32.0, 25.6)                     # pixlar i 128-bilden
        (p,) = decode_palms(self.scores, self.reg.flatten(), self.anchors)
        cx, cy = self.anchors[600]
        self.assertAlmostEqual(p.score, 0.9, places=5)
        self.assertAlmostEqual(p.x0, cx + 0.1 - 0.125, places=5)
        self.assertAlmostEqual(p.x1, cx + 0.1 + 0.125, places=5)
        self.assertAlmostEqual(p.y0, cy - 0.05 - 0.1, places=5)
        self.assertAlmostEqual(p.y1, cy - 0.05 + 0.1, places=5)

    def test_the_seven_points_follow_the_anchor(self):
        self.scores[600] = logit(0.9)
        self.reg[600, :4] = (0.0, 0.0, 32.0, 32.0)
        self.reg[600, 4:6] = (12.8, 25.6)                               # handleden
        self.reg[600, 8:10] = (-6.4, -12.8)                             # långfingrets knoge
        (p,) = decode_palms(self.scores, self.reg, self.anchors)
        cx, cy = self.anchors[600]
        self.assertEqual(len(p.kps), 7)
        self.assertAlmostEqual(p.kps[0][0], cx + 0.1, places=5)
        self.assertAlmostEqual(p.kps[0][1], cy + 0.2, places=5)
        self.assertAlmostEqual(p.kps[2][0], cx - 0.05, places=5)
        self.assertAlmostEqual(p.kps[2][1], cy - 0.1, places=5)
        self.assertAlmostEqual(p.kps[1][0], cx, places=5)                # inga värden: ankarets mitt

    def test_threshold_and_broken_boxes(self):
        self.scores[10] = logit(0.45)                                    # under 0,5
        self.reg[10, 2:4] = (10.0, 10.0)
        self.scores[20] = logit(0.8)
        self.reg[20, 2:4] = (-5.0, 10.0)                                 # negativ bredd: trasig
        self.scores[30] = logit(0.6)
        self.reg[30, 2:4] = (10.0, 10.0)
        self.assertEqual([round(p.score, 2) for p in decode_palms(self.scores, self.reg, self.anchors)], [0.6])
        self.assertEqual(len(decode_palms(self.scores, self.reg, self.anchors, threshold=0.4)), 2)

    def test_extreme_raw_scores_give_no_warning(self):
        import warnings
        self.scores[:] = -1000.0                                         # som på kameran 9/11
        self.scores[5] = 1000.0
        self.reg[5, 2:4] = (10.0, 10.0)
        with warnings.catch_warnings():
            warnings.simplefilter("error")                               # en varning blir ett fel
            (p,) = decode_palms(self.scores, self.reg, self.anchors)
        self.assertAlmostEqual(p.score, 1.0)

    def test_nothing_found(self):
        self.assertEqual(decode_palms(self.scores, self.reg, self.anchors), [])


class NmsTest(unittest.TestCase):
    def test_keeps_the_best_box_per_hand(self):
        a = Palm(0.9, 0.1, 0.1, 0.3, 0.3)
        b = Palm(0.7, 0.12, 0.12, 0.32, 0.32)                            # samma hand
        c = Palm(0.6, 0.6, 0.6, 0.8, 0.8)                                # en annan hand
        self.assertEqual(non_max_suppression([b, c, a]), [a, c])
        self.assertEqual(non_max_suppression([a, b, c], keep=1), [a])
        self.assertAlmostEqual(iou(a, a), 1.0)
        self.assertEqual(iou(a, c), 0.0)


class FrameTest(unittest.TestCase):
    def test_letterbox_for_4k_and_1080p(self):
        self.assertEqual(letterbox_rows(3840, 2160), (72, 28, 28))
        self.assertEqual(letterbox_rows(1920, 1080), (72, 28, 28))

    def test_square_coordinates_back_to_the_camera_image(self):
        # 16:9 i en kvadrat: bilden täcker y 0,21875-0,78125 av kvadraten
        p = square_to_frame(Palm(0.8, 0.25, 0.21875, 0.5, 0.5), 3840, 2160)
        self.assertEqual((p.x0, p.x1, p.score), (0.25, 0.5, 0.8))
        self.assertAlmostEqual(p.y0, 0.0)
        self.assertAlmostEqual(p.y1, 0.5)
        edge = square_to_frame(Palm(0.8, -0.1, 0.1, 1.2, 0.9), 3840, 2160)   # utanför: klipps
        self.assertEqual((edge.x0, edge.y0, edge.x1, edge.y1), (0.0, 0.0, 1.0, 1.0))


class OverlapTest(unittest.TestCase):
    region = NearRegion(0.4, 0.5, 0.7, 1.0, depth_m=0.45, area=0.1)

    def test_a_hand_inside_or_just_outside_the_box_counts(self):
        self.assertTrue(overlaps(self.region, Palm(0.9, 0.45, 0.6, 0.55, 0.7)))    # helt inne
        self.assertTrue(overlaps(self.region, Palm(0.9, 0.36, 0.6, 0.42, 0.7)))    # sticker ut till vänster
        self.assertFalse(overlaps(self.region, Palm(0.9, 0.05, 0.1, 0.15, 0.2)))   # någon annanstans
        self.assertFalse(overlaps(self.region, Palm(0.9, 0.5, 0.5, 0.5, 0.6)))     # ingen yta

    def test_a_small_corner_is_not_enough(self):
        self.assertFalse(overlaps(self.region, Palm(0.9, 0.7, 0.3, 0.9, 0.5)))     # bara hörnet i marginalen


class SummarizeTest(unittest.TestCase):
    def test_counts(self):
        rows = [(True, True, True), (True, True, False), (True, False, False), (False, True, False),
                (False, False, False), (True, True, True)]
        self.assertEqual(summarize(rows), {"bilder": 6, "narmast": 4, "hand": 4, "bekraftad": 2,
                                           "narmast_utan_hand": 2, "hand_utan_narmast": 1, "ingenting": 1})


class SquareCropTest(unittest.TestCase):
    def test_square_around_the_box_with_margin(self):
        region = NearRegion(0.4, 0.4, 0.6, 0.6, depth_m=0.45, area=0.04)   # 768 x 432 px i 4K
        x, y, side = square_crop(region, 3840, 2160)
        self.assertEqual(side, round(768 * 1.3))                         # längsta sidan + 15 % runt om
        self.assertAlmostEqual(x + side / 2, 1920, delta=1)              # samma mitt
        self.assertAlmostEqual(y + side / 2, 1080, delta=1)

    def test_moved_inside_the_image_at_the_edges(self):
        bottom = NearRegion(0.3, 0.8, 0.7, 1.0, depth_m=0.45, area=0.08)   # varan längst ner, 1536 px bred
        x, y, side = square_crop(bottom, 3840, 2160)
        self.assertEqual(side, 1997)
        self.assertEqual(y + side, 2160)                                 # flyttad upp, slutar vid nederkanten
        wide = NearRegion(0.2, 0.8, 0.8, 1.0, depth_m=0.45, area=0.12)     # 2304 px bred
        x, y, side = square_crop(wide, 3840, 2160)
        self.assertEqual((side, y), (2160, 0))                           # högst bildhöjden
        self.assertEqual(x + side // 2, 1920)
        corner = NearRegion(0.9, 0.0, 1.0, 0.1, depth_m=0.45, area=0.01)
        x, y, side = square_crop(corner, 3840, 2160)
        self.assertEqual((x + side, y), (3840, 0))                       # i hörnet, helt i bilden

    def test_a_tiny_box_gets_a_minimum_size(self):
        tiny = NearRegion(0.5, 0.5, 0.51, 0.51, depth_m=0.45, area=0.0001)
        self.assertEqual(square_crop(tiny, 3840, 2160)[2], 432)          # 20 % av bildhöjden

    def test_back_to_the_camera_image(self):
        p = crop_to_frame(Palm(0.7, 0.25, 0.5, 0.75, 1.0), (1000, 500, 800), 3840, 2160)
        self.assertAlmostEqual(p.x0, 1200 / 3840)
        self.assertAlmostEqual(p.x1, 1600 / 3840)
        self.assertAlmostEqual(p.y0, 900 / 2160)
        self.assertAlmostEqual(p.y1, 1300 / 2160)
        self.assertEqual(p.score, 0.7)
        edge = crop_to_frame(Palm(0.7, -0.5, -0.5, 1.5, 1.5), (0, 0, 2160), 3840, 2160)
        self.assertEqual((edge.x0, edge.y0, edge.y1), (0.0, 0.0, 1.0))


class MedianTextTest(unittest.TestCase):
    def test_median_and_range(self):
        self.assertEqual(median_text([0.9, 0.5, 0.7]), "0.70 (0.50-0.90)")
        self.assertEqual(median_text([39.4, 41.0], "{:.0f}"), "41 (39-41)")
        self.assertEqual(median_text([]), "-")


class RuleTest(unittest.TestCase):
    def test_a_hand_seen_in_the_box_counts_for_two_seconds(self):
        rows = [(0.0, True, False),       # blå, ingen hand än
                (0.5, True, True),        # hand i rutan
                (1.0, True, False),
                (2.5, True, False),       # precis 2 s efter
                (3.0, True, False),       # 2,5 s efter: inte längre
                (3.5, False, False),      # ingen blå ruta: räknas inte
                (4.0, True, True)]
        self.assertEqual(confirmed_within(rows), (4, 6))
        self.assertEqual(confirmed_within(rows, window=0.0), (2, 6))

    def test_a_hand_outside_any_box_does_not_count(self):
        self.assertEqual(confirmed_within([(0.0, False, True), (0.5, True, False)]), (0, 1))
        self.assertEqual(confirmed_within([]), (0, 0))

    def test_texts(self):
        self.assertEqual(share_text(7, 10), "7 av 10 (70 %)")
        self.assertEqual(share_text(0, 47), "0 av 47 (0 %)")
        self.assertEqual(share_text(0, 0), "-")
        self.assertEqual(mosaic_path(), "logs/handmodell.jpg")
        self.assertEqual(mosaic_path("dorr"), "logs/handmodell_dorr.jpg")


class HandRectTest(unittest.TestCase):
    @staticmethod
    def palm(wrist, middle):
        return Palm(0.9, 0.4, 0.4, 0.6, 0.6, (wrist, (0.5, 0.5), middle, (0, 0), (0, 0), (0, 0), (0, 0)))

    def assertPoints(self, got, want):
        for g, w in zip(got, want):
            self.assertAlmostEqual(g[0], w[0], places=4)
            self.assertAlmostEqual(g[1], w[1], places=4)

    def test_an_upright_hand_is_moved_towards_the_fingers_and_enlarged(self):
        # handleden nere, långfingret uppe: ingen vridning. Handflatan 20 px, rutan 2,6 x 20 = 52 px,
        # mitten en halv handflata (10 px) uppåt.
        pts = hand_rect(self.palm((0.5, 0.6), (0.5, 0.4)), 0, 0, 100)
        self.assertPoints(pts, [(24, 66), (24, 14), (76, 14), (76, 66)])   # nere v, uppe v, uppe h, nere h

    def test_a_hand_pointing_right_is_turned(self):
        # fingrarna åt höger: mitten flyttas åt höger, och bildens "uppe" (hörn 1 -> 2) är högerkanten
        pts = hand_rect(self.palm((0.4, 0.5), (0.6, 0.5)), 0, 0, 100)
        self.assertPoints(pts, [(34, 24), (86, 24), (86, 76), (34, 76)])

    def test_the_square_is_placed_in_the_camera_image(self):
        moved = hand_rect(self.palm((0.5, 0.6), (0.5, 0.4)), 10, -20, 100)
        self.assertPoints(moved, [(34, 46), (34, -6), (86, -6), (86, 46)])
        big = hand_rect(self.palm((0.5, 0.6), (0.5, 0.4)), 0, 0, 200)
        self.assertPoints(big, [(48, 132), (48, 28), (152, 28), (152, 132)])

    def test_above_text(self):
        self.assertEqual(above_text([0.1, 0.6, 0.95], 0.5), "2 av 3 över 0.5")
        self.assertEqual(above_text([], 0.5), "-")


class ShrinkTest(unittest.TestCase):
    def test_the_hand_box_ends_up_between_one_and_two_model_sizes(self):
        def box(side):
            return [(0, side), (0, 0), (side, 0), (side, side)]
        self.assertEqual(shrink_factor(box(200)), 1)                     # mindre än modellen: ingen förminskning
        self.assertEqual(shrink_factor(box(447)), 1)
        self.assertEqual(shrink_factor(box(448)), 2)
        self.assertEqual(shrink_factor(box(1000)), 4)                    # 250 px kvar
        self.assertEqual(shrink_factor(box(2000)), 8)
        for side in range(100, 3000, 37):
            k = shrink_factor(box(side))
            self.assertTrue(side / k < 2 * 224 and (k == 1 or side / k >= 224), side)

    def test_a_turned_box_uses_its_side_not_its_width(self):
        d = 1000 / 2 ** 0.5                                              # 1000 px sida, vriden 45 grader
        self.assertEqual(shrink_factor([(0, 0), (0, 0), (d, d), (0, 0)]), 4)


if __name__ == "__main__":
    unittest.main()
