import unittest

import numpy as np

from hand_region import NearRegion
from tools.handmodell import (Palm, decode_palms, iou, letterbox_rows, non_max_suppression, overlaps,
                              palm_anchors, square_to_frame, summarize)


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

    def test_threshold_and_broken_boxes(self):
        self.scores[10] = logit(0.45)                                    # under 0,5
        self.reg[10, 2:4] = (10.0, 10.0)
        self.scores[20] = logit(0.8)
        self.reg[20, 2:4] = (-5.0, 10.0)                                 # negativ bredd: trasig
        self.scores[30] = logit(0.6)
        self.reg[30, 2:4] = (10.0, 10.0)
        self.assertEqual([round(p.score, 2) for p in decode_palms(self.scores, self.reg, self.anchors)], [0.6])
        self.assertEqual(len(decode_palms(self.scores, self.reg, self.anchors, threshold=0.4)), 2)

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


if __name__ == "__main__":
    unittest.main()
