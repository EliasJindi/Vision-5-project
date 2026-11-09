import contextlib
import io
import unittest
from unittest import mock

from voice_guidance import (ActionKind, AimConvention, ConsoleSpeaker, DictProductCatalog, GuidanceEngine,
                            GuidanceMode, GuidanceSession, GuidanceVoice, create_session)
import voice_guidance.session as session_module

from tests.helpers import EAN_A, FULL_CORNERS, THIN_CORNERS, FakePublisher, FakeSpeaker, record

PRODUCTS = {EAN_A: [{"namn": "Tomatpure"}]}


def build(link=None, speaker=None):
    link = link or FakePublisher()
    speaker = speaker or FakeSpeaker()
    engine = GuidanceEngine(DictProductCatalog(PRODUCTS))
    return GuidanceSession(engine, GuidanceVoice(speaker, AimConvention.HEAD), link), link, speaker


class GuidanceSessionTest(unittest.TestCase):
    def test_reliable_reads_are_confirmed_by_name_and_published(self):
        session, link, speaker = build()
        self.assertIsNone(session.on_frame(1.0, [record(1.0, filter=[])]))
        action = session.on_frame(1.5, [record(1.5, filter=[])])
        self.assertEqual(action.kind, ActionKind.CONFIRMED)
        self.assertEqual(speaker.texts, ["Tomatpure. Tillagd."])
        guidance = link.of_type("guidance")
        self.assertEqual(guidance, [{"type": "guidance", "t": 1.5, "action": "confirmed", "ean": EAN_A,
                                     "name": "Tomatpure", "details": [], "basket": "added",
                                     "text": "Tomatpure. Tillagd."}])
        self.assertEqual(session.basket.items(), [(EAN_A, "Tomatpure")])

    def test_seen_codes_and_the_hand_flag_reach_the_engine(self):
        session, _, _ = build()
        with mock.patch.object(session._engine, "update", return_value=None) as update:
            session.on_frame(1.0, [], [(0.5, 0.9)], True)
            session.on_frame(1.5, [])
        first, second = update.call_args_list[0].args[0], update.call_args_list[1].args[0]
        self.assertEqual((first.seen, first.hand), (((0.5, 0.9),), True))
        self.assertEqual((second.seen, second.hand), ((), False))         # som förut

    def test_the_same_product_scanned_again_is_not_added_twice(self):
        session, link, speaker = build()
        for t in (1.0, 1.5, 10.0, 10.5):   # borta i över 5 s mellan: bekräftas igen
            session.on_frame(t, [record(t, filter=[])])
        self.assertEqual(speaker.texts, ["Tomatpure. Tillagd.", "Tomatpure. Finns redan i korgen."])
        self.assertEqual(len(session.basket), 1)
        self.assertEqual([g["basket"] for g in link.of_type("guidance")], ["added", "already"])

    def test_unknown_products_and_guidance_never_go_in_the_basket(self):
        session, link, speaker = build()
        for t in (1.0, 1.5):
            session.on_frame(t, [record(t, ean="7311043006847", filter=[])])
        session.on_frame(5.0, [record(5.0, corners=THIN_CORNERS, filter=["tunn"])])
        self.assertEqual(speaker.texts[0], "Okänd vara.")
        self.assertEqual(len(session.basket), 0)
        self.assertTrue(all(g["basket"] is None for g in link.of_type("guidance")))

    def test_every_record_is_published_as_a_read_event(self):
        session, link, _ = build()
        session.on_frame(1.0, [record(1.0, filter=[]), record(1.0, ean="7311043006847", filter=["tunn"])])
        reads = link.of_type("read")
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[0]["ean"], EAN_A)
        self.assertEqual(reads[0]["hornen"], FULL_CORNERS)

    def test_the_session_type_cannot_be_overwritten_by_a_record_field(self):
        session, link, _ = build()
        session.on_frame(1.0, [{**record(1.0, filter=[]), "type": "something else"}])
        self.assertEqual(link.events[0]["type"], "read")

    def test_unsure_code_is_guided(self):
        session, _, speaker = build()
        session.on_frame(1.0, [record(1.0, corners=THIN_CORNERS, filter=["tunn"])])
        self.assertEqual(len(speaker.texts), 1)
        self.assertIn("närmare", speaker.texts[0])

    def test_frames_without_reads_are_silent_but_advance_time(self):
        session, _, speaker = build()
        session.on_frame(1.0, [record(1.0, filter=[])])
        self.assertIsNone(session.on_frame(4.5, []))   # under 4 s utan kod: ännu inget "hittar ingen streckkod"
        session.on_frame(7.0, [record(7.0, filter=[])])    # mer än 2 s efter första läsningen: den räknas inte
        session.on_frame(7.5, [record(7.5, filter=[])])
        self.assertEqual(speaker.texts, ["Tomatpure. Tillagd."])   # bara en bekräftelse: första läsningen var ensam

    def test_a_broken_record_is_skipped_with_one_warning(self):
        session, link, _ = build()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for t in (1.0, 2.0, 3.0):
                session.on_frame(t, [{"t": t, "ean": EAN_A}])
        self.assertEqual(out.getvalue().count("trasig loggrad"), 1)
        self.assertEqual(len(link.of_type("read")), 3)   # den publiceras ändå: länken visar vad skannern såg

    def test_session_without_engine_only_publishes(self):
        link = FakePublisher()
        session = GuidanceSession(None, None, link)
        self.assertIsNone(session.on_frame(1.0, [record(1.0, filter=[])]))
        self.assertEqual(len(link.of_type("read")), 1)
        self.assertEqual(link.of_type("guidance"), [])

    def test_engine_and_voice_must_come_together(self):
        with self.assertRaises(ValueError):
            GuidanceSession(GuidanceEngine(DictProductCatalog({})), None, FakePublisher())

    def test_close_closes_the_link(self):
        session, link, _ = build()
        session.close()
        self.assertTrue(link.closed)


class CreateSessionTest(unittest.TestCase):
    def test_off_without_link_is_inert(self):
        session = create_session(PRODUCTS, GuidanceMode.OFF)
        self.assertIsNone(session.on_frame(1.0, [record(1.0, filter=[])]))

    def test_text_mode_prints_instead_of_speaking(self):
        out = io.StringIO()
        session = create_session(PRODUCTS, GuidanceMode.TEXT)
        with contextlib.redirect_stdout(out):
            session.on_frame(1.0, [record(1.0, corners=THIN_CORNERS, filter=["tunn"])])
        self.assertIn("Sakta närmare.", out.getvalue())

    def test_link_without_guidance_still_plays_say_commands(self):
        speaker = FakeSpeaker()
        with mock.patch.object(session_module, "_voice_speaker", return_value=speaker), \
                contextlib.redirect_stdout(io.StringIO()):
            session = create_session(PRODUCTS, GuidanceMode.OFF, link_port=0)
        self.addCleanup(session.close)
        self.assertIsNotNone(session._link.port)
        session._link._on_say(session_module.SayCommand("Hej från C#"))
        self.assertEqual(speaker.said, [("Hej från C#", "link")])

    def test_voice_mode_falls_back_to_console_when_audio_is_unavailable(self):
        out = io.StringIO()
        with mock.patch.object(session_module, "AudioManagerSpeaker", side_effect=RuntimeError("ingen piper")):
            with contextlib.redirect_stdout(out):
                speaker = session_module._voice_speaker()
        self.assertIsInstance(speaker, ConsoleSpeaker)
        self.assertIn("ingen piper", out.getvalue())


if __name__ == "__main__":
    unittest.main()
