import unittest

from phrases import AIM_PHRASES, GUIDANCE_PHRASES, guidance_phrases, guidance_text
from voice_guidance import (ActionKind, AimConvention, AudioManagerSpeaker, ConsoleSpeaker,
                            DictProductCatalog, EmptyProductCatalog, GuidanceAction, GuidanceVoice)

from tests.helpers import EAN_A, FakeSpeaker


class PhrasesTest(unittest.TestCase):
    def test_every_action_kind_has_text_in_both_conventions(self):
        for convention in AimConvention:
            for kind in ActionKind:
                with self.subTest(kind=kind, convention=convention):
                    text = guidance_text(kind.value, convention.value, name="Tomatpure")
                    self.assertTrue(text.endswith("."))

    def test_confirmed_says_the_name_capitalised(self):
        self.assertEqual(guidance_text("confirmed", name="tomatpure"), "Tomatpure.")

    def test_confirmed_without_name_is_an_error(self):
        with self.assertRaises(ValueError):
            guidance_text("confirmed")

    def test_unknown_kind_or_convention_is_an_error(self):
        with self.assertRaises(ValueError):
            guidance_text("flying")
        with self.assertRaises(ValueError):
            guidance_text("code_left", convention="foot")

    def test_head_and_hand_give_opposite_directions(self):
        self.assertEqual(guidance_text("code_left", "head"), "Lite åt vänster.")
        self.assertEqual(guidance_text("code_left", "hand"), "Lite åt höger.")
        self.assertEqual(guidance_text("code_above", "head"), "Lite uppåt.")
        self.assertEqual(guidance_text("code_above", "hand"), "Lite nedåt.")

    def test_prewarm_list_covers_every_fixed_phrase_once(self):
        phrases = guidance_phrases()
        self.assertEqual(phrases, sorted(set(phrases)))
        for text in list(GUIDANCE_PHRASES.values()) + [t for aim in AIM_PHRASES.values() for t in aim.values()]:
            self.assertIn(text, phrases)


class GuidanceVoiceTest(unittest.TestCase):
    def test_announce_speaks_and_returns_the_text(self):
        speaker = FakeSpeaker()
        text = GuidanceVoice(speaker).announce(GuidanceAction(ActionKind.CLOSER))
        self.assertEqual(text, "Lite närmare.")
        self.assertEqual(speaker.said, [("Lite närmare.", "closer")])

    def test_convention_decides_the_words(self):
        action = GuidanceAction(ActionKind.CODE_RIGHT)
        self.assertEqual(GuidanceVoice(FakeSpeaker(), AimConvention.HEAD).announce(action), "Lite åt höger.")
        self.assertEqual(GuidanceVoice(FakeSpeaker(), AimConvention.HAND).announce(action), "Lite åt vänster.")

    def test_confirmation_says_the_product_name(self):
        speaker = FakeSpeaker()
        GuidanceVoice(speaker).announce(GuidanceAction(ActionKind.CONFIRMED, ean=EAN_A, name="Tomatpure"))
        self.assertEqual(speaker.texts, ["Tomatpure."])


class AudioManagerSpeakerTest(unittest.TestCase):
    def test_speaks_on_priority_three_so_it_never_outranks_safety(self):
        calls = []

        class FakeAudio:
            def speak(self, text, priority, key=None):
                calls.append((text, priority, key))

        AudioManagerSpeaker(audio=FakeAudio()).say("Lite närmare.", key="closer")
        self.assertEqual(calls, [("Lite närmare.", 3, "closer")])


class ConsoleSpeakerTest(unittest.TestCase):
    def test_prints_the_text(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ConsoleSpeaker().say("Håll stilla.", key="hold_still")
        self.assertIn("Håll stilla.", out.getvalue())


class CatalogTest(unittest.TestCase):
    def test_dict_catalog_returns_the_first_name_or_none(self):
        catalog = DictProductCatalog({EAN_A: [{"namn": " Tomatpure "}, {"namn": "annan"}], "1": [{"namn": ""}]})
        self.assertEqual(catalog.name_of(EAN_A), "Tomatpure")
        self.assertIsNone(catalog.name_of("0000000000000"))
        self.assertIsNone(catalog.name_of("1"))

    def test_empty_catalog_knows_nothing(self):
        self.assertIsNone(EmptyProductCatalog().name_of(EAN_A))

    def test_from_geojson_reads_ean_and_name(self):
        import json
        import os
        import tempfile
        features = [{"properties": {"ean": EAN_A, "namn": "Tomatpure"}}, {"properties": {"namn": "utan ean"}}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "karta.geojson")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"features": features}, f)
            self.assertEqual(DictProductCatalog.from_geojson(path).name_of(EAN_A), "Tomatpure")


if __name__ == "__main__":
    unittest.main()
