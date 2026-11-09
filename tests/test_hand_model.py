import hashlib
import os
import tempfile
import unittest

import hand_model
from hand_model import HandGate, HandModel, ModelError, Palm, ensure_model
from hand_region import NearRegion


class HandGateTest(unittest.TestCase):
    def test_a_confirmed_hand_counts_for_two_seconds(self):
        gate = HandGate()
        self.assertFalse(gate.active(0.0))                               # ingen hand än
        gate.update(1.0, True)
        self.assertTrue(gate.active(1.0))
        gate.update(2.0, False)                                          # missad i en bildruta: gäller ändå
        self.assertTrue(gate.active(3.0))                                # precis 2 s
        self.assertFalse(gate.active(3.01))
        gate.update(4.0, True)
        self.assertTrue(gate.active(4.5))

    def test_the_window_can_be_changed(self):
        gate = HandGate(window=0.0)
        gate.update(1.0, True)
        self.assertTrue(gate.active(1.0))
        self.assertFalse(gate.active(1.5))


class ModelFileTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = os.path.join(self.folder.name, "m.blob")

    def write(self, data):
        with open(self.path, "wb") as f:
            f.write(data)
        return hashlib.sha256(data).hexdigest()

    def test_the_right_file_is_accepted(self):
        digest = self.write(b"modell")
        self.assertEqual(ensure_model(self.path, "http://inte.anvand", digest, download=False), self.path)

    def test_a_missing_file_is_not_downloaded_by_the_scanner(self):
        with self.assertRaises(ModelError):
            ensure_model(self.path, "http://inte.anvand", "0" * 64, download=False)

    def test_a_wrong_file_is_refused_and_kept_when_not_downloading(self):
        self.write(b"fel fil")
        with self.assertRaises(ModelError):
            ensure_model(self.path, "http://inte.anvand", "0" * 64, download=False)
        self.assertTrue(os.path.exists(self.path))                       # skannern raderar inget

    def test_the_tool_removes_a_wrong_file_so_the_next_run_downloads_it_again(self):
        self.write(b"trasig nedladdning")
        with self.assertRaises(ModelError):
            ensure_model(self.path, "http://inte.anvand", "0" * 64, download=True)
        self.assertFalse(os.path.exists(self.path))

    def test_load_without_models_gives_a_reason(self):
        model, why = hand_model.load(self.path, self.path)
        self.assertIsNone(model)
        self.assertIn("saknas", why)

    def test_load_with_both_models(self):
        palm = self.write(b"handflata")
        lm_path = os.path.join(self.folder.name, "lm.blob")
        with open(lm_path, "wb") as f:
            f.write(b"landmarke")
        lm = hashlib.sha256(b"landmarke").hexdigest()
        old = hand_model.MODEL_SHA256, hand_model.LM_SHA256
        hand_model.MODEL_SHA256, hand_model.LM_SHA256 = palm, lm
        try:
            model, why = hand_model.load(self.path, lm_path)
        finally:
            hand_model.MODEL_SHA256, hand_model.LM_SHA256 = old
        self.assertIsNotNone(model)
        self.assertEqual(why, "")
        self.assertEqual((model.palm_threshold, model.lm_threshold), (0.5, 0.5))


class CheckTest(unittest.TestCase):
    """HandModel.check utan kamera: handflatorna och landmärkesvärdena byts ut."""
    region = NearRegion(0.4, 0.5, 0.7, 1.0, depth_m=0.45, area=0.1)

    def model(self, palms, values):
        m = HandModel()
        m.palms = lambda color: palms
        asked = []
        def score(color, palm, shrunk):
            asked.append(palm)
            return values[palm.score]
        m.hand_score = score
        return m, asked

    def test_only_palms_in_the_blue_box_are_checked(self):
        inside, outside = Palm(0.6, 0, 0, 1, 1), Palm(0.7, 0, 0, 1, 1)
        palms = [(inside, Palm(0.6, 0.45, 0.6, 0.55, 0.7)),           # i den blå rutan
                 (outside, Palm(0.7, 0.05, 0.1, 0.15, 0.2))]           # på dörrkarmen
        m, asked = self.model(palms, {0.6: 0.91, 0.7: 0.99})
        self.assertEqual(m.check(None, self.region), 0.91)
        self.assertEqual(asked, [inside])
        self.assertEqual(len(m.ms), 1)

    def test_no_palm_in_the_box_gives_zero(self):
        m, asked = self.model([(Palm(0.7, 0, 0, 1, 1), Palm(0.7, 0.05, 0.1, 0.15, 0.2))], {0.7: 0.99})
        self.assertEqual(m.check(None, self.region), 0.0)
        self.assertEqual(asked, [])

    def test_the_best_of_at_most_two_hands(self):
        fr = Palm(0.5, 0.45, 0.6, 0.55, 0.7)
        palms = [(Palm(s, 0, 0, 1, 1), fr) for s in (0.51, 0.52, 0.53)]
        m, asked = self.model(palms, {0.51: 0.2, 0.52: 0.8, 0.53: 0.95})
        self.assertEqual(m.check(None, self.region), 0.8)              # den tredje kontrolleras inte
        self.assertEqual(len(asked), 2)


if __name__ == "__main__":
    unittest.main()
