import unittest

from phrases import AIM_PHRASES, GUIDANCE_PHRASES, guidance_phrases, guidance_text
from voice_guidance import (ActionKind, AimConvention, AudioManagerSpeaker, ConsoleSpeaker,
                            DictProductCatalog, EmptyProductCatalog, GuidanceAction, GuidanceVoice)

from tests.helpers import EAN_A, FakeSpeaker


class PhrasesTest(unittest.TestCase):
    def test_every_action_kind_has_text_in_both_conventions(self):
        for convention in AimConvention:
            for kind in (k for k in ActionKind if k is not ActionKind.CODE_SEEN):   # pipet är inget tal
                with self.subTest(kind=kind, convention=convention):
                    text = guidance_text(kind.value, convention.value, name="Tomatpure")
                    self.assertTrue(text.endswith("."))

    def test_confirmed_says_the_name_capitalised(self):
        self.assertEqual(guidance_text("confirmed", name="tomatpure"), "Tomatpure.")

    def test_confirmed_reads_the_details_after_the_name(self):
        self.assertEqual(guidance_text("confirmed", name="tomatpure", details=("140 gram", "hylla 3")),
                         "Tomatpure. 140 gram. Hylla 3.")
        self.assertEqual(guidance_text("confirmed", name="Mjölk.", details=("Laktosfri!",)), "Mjölk. Laktosfri!")

    def test_the_cue_has_no_words(self):
        with self.assertRaises(ValueError):
            guidance_text("code_seen")

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

    def test_cue_is_a_beep_not_speech(self):
        speaker = FakeSpeaker()
        self.assertEqual(GuidanceVoice(speaker).announce(GuidanceAction(ActionKind.CODE_SEEN)), "♪")
        self.assertEqual(speaker.said, [("♪", "cue")])

    def test_confirmation_reads_the_details(self):
        speaker = FakeSpeaker()
        GuidanceVoice(speaker).announce(GuidanceAction(ActionKind.CONFIRMED, ean=EAN_A, name="Tomatpure",
                                                       details=("140 gram",)))
        self.assertEqual(speaker.texts, ["Tomatpure. 140 gram."])

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

    def test_cue_plays_a_ready_wav_with_a_short_shelf_life(self):
        import os
        import tempfile
        import wave
        from tts_engine import wav_duration
        from voice_guidance.voice import CUE_TTL_S
        calls = []

        class FakeAudio:
            def speak(self, text, priority, key=None, wav=None, ttl=None):
                calls.append((priority, key, wav, ttl))

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "pip.wav")
            AudioManagerSpeaker(audio=FakeAudio(), cue_path=path).cue()
            self.assertEqual(calls, [(3, "cue", path, CUE_TTL_S)])
            self.assertAlmostEqual(wav_duration(path), 0.07, places=2)   # samma kontroll som ljudkön gör
            with wave.open(path) as f:
                self.assertEqual((f.getnchannels(), f.getsampwidth()), (1, 2))


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
        self.assertEqual(EmptyProductCatalog().details_of(EAN_A), ())

    def test_details_come_from_the_info_field_as_text_or_list(self):
        catalog = DictProductCatalog({EAN_A: [{"namn": "Tomatpure", "info": ["140 gram", " ", "hylla 3"]}],
                                      "2": [{"namn": "Mjölk", "info": "laktosfri"}], "3": [{"namn": "Salt"}]})
        self.assertEqual(catalog.details_of(EAN_A), ("140 gram", "hylla 3"))
        self.assertEqual(catalog.details_of("2"), ("laktosfri",))
        self.assertEqual(catalog.details_of("3"), ())
        self.assertEqual(catalog.details_of("okänd"), ())

    def test_too_much_info_is_refused_rather_than_read_out(self):
        from voice_guidance.catalog import parse_details
        for bad in (["a", "b", "c"], ["x" * 41], {"vikt": "140 g"}, 140):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_details(bad)

    def test_announcements_list_every_confirmation_once_for_prewarm(self):
        catalog = DictProductCatalog({EAN_A: [{"namn": "Tomatpure", "info": "140 gram"}, {"namn": "Tomatpure"}],
                                      "2": [{"namn": "Mjölk"}], "3": [{"namn": ""}]})
        self.assertEqual(catalog.announcements(), ["Mjölk.", "Tomatpure. 140 gram."])

    def test_from_geojson_reads_ean_and_name(self):
        import json
        import os
        import tempfile
        features = [{"properties": {"ean": EAN_A, "namn": "Tomatpure", "info": ["140 gram"]}},
                    {"properties": {"namn": "utan ean"}}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "karta.geojson")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"features": features}, f)
            catalog = DictProductCatalog.from_geojson(path)
            self.assertEqual((catalog.name_of(EAN_A), catalog.details_of(EAN_A)), ("Tomatpure", ("140 gram",)))


if __name__ == "__main__":
    unittest.main()
