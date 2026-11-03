import unittest

from voice_guidance import ActionKind, CodeRead, GuidanceAction

from tests.helpers import EAN_A, FULL_CORNERS, THIN_CORNERS, record


class CodeReadFromRecordTest(unittest.TestCase):
    def test_full_code_is_reliable_and_centered_in_frame(self):
        read = CodeRead.from_record(record(1.0, corners=FULL_CORNERS, filter=[]))
        self.assertEqual(read.ean, EAN_A)
        self.assertFalse(read.thin)
        self.assertTrue(read.reliable)
        self.assertAlmostEqual(read.center[0], 845.75 / 1920, places=4)
        self.assertAlmostEqual(read.center[1], 647.5 / 1080, places=4)

    def test_filter_field_decides_thinness_when_present(self):
        self.assertTrue(CodeRead.from_record(record(1.0, filter=["tunn"])).thin)
        self.assertFalse(CodeRead.from_record(record(1.0, filter=["orimligt djup"])).thin)

    def test_old_logs_without_filter_field_are_recomputed_from_corners(self):
        self.assertTrue(CodeRead.from_record(record(1.0, corners=THIN_CORNERS)).thin)
        self.assertFalse(CodeRead.from_record(record(1.0, corners=FULL_CORNERS)).thin)

    def test_invalid_checksum_gives_no_ean_and_is_never_reliable(self):
        read = CodeRead.from_record(record(1.0, ean=None, filter=[]))
        self.assertIsNone(read.ean)
        self.assertFalse(read.reliable)

    def test_thin_read_is_not_reliable(self):
        self.assertFalse(CodeRead.from_record(record(1.0, corners=THIN_CORNERS)).reliable)

    def test_center_is_clamped_to_the_frame(self):
        rec = record(1.0, corners=[[1900, 1070], [2000, 1070], [2000, 1200], [1900, 1200]], filter=[])
        self.assertEqual(CodeRead.from_record(rec).center, (1.0, 1.0))

    def test_missing_field_raises_value_error(self):
        rec = record(1.0)
        del rec["hornen"]
        with self.assertRaises(ValueError):
            CodeRead.from_record(rec)

    def test_wrong_shapes_raise_value_error(self):
        for bad in ({"bild": [0, 1080]}, {"bild": [1920]}, {"hornen": [[1, 2]]}, {"hornen": "x"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    CodeRead.from_record({**record(1.0), **bad})

    def test_distance_from_center(self):
        self.assertEqual(CodeRead(EAN_A, (0.5, 0.5), False).distance_from_center(), 0.0)
        self.assertAlmostEqual(CodeRead(EAN_A, (0.8, 0.9), False).distance_from_center(), 0.5)


class GuidanceActionTest(unittest.TestCase):
    def test_confirmation_requires_ean_and_name(self):
        with self.assertRaises(ValueError):
            GuidanceAction(ActionKind.CONFIRMED)
        with self.assertRaises(ValueError):
            GuidanceAction(ActionKind.CONFIRMED, ean=EAN_A)

    def test_unknown_product_requires_ean_only(self):
        with self.assertRaises(ValueError):
            GuidanceAction(ActionKind.UNKNOWN_PRODUCT)
        self.assertEqual(GuidanceAction(ActionKind.UNKNOWN_PRODUCT, ean=EAN_A).name, None)

    def test_guidance_needs_nothing(self):
        self.assertEqual(GuidanceAction(ActionKind.CLOSER).ean, None)


if __name__ == "__main__":
    unittest.main()
