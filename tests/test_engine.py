import unittest

from voice_guidance import (ActionKind, CodeRead, DictProductCatalog, EmptyProductCatalog, FrameObservation, GuidanceAction,
                            GuidanceConfig, GuidanceEngine)

from tests.helpers import EAN_A, EAN_B, frame, read

CATALOG = DictProductCatalog({EAN_A: [{"namn": "Tomatpure"}]})   # EAN_B är medvetet okänd


def kinds(actions):
    return [a.kind if a else None for a in actions]


class ConfirmationTest(unittest.TestCase):
    def setUp(self):
        self.engine = GuidanceEngine(CATALOG)

    def test_known_product_is_confirmed_after_two_reliable_reads(self):
        self.assertIsNone(self.engine.update(frame(0.0, read())))
        self.assertEqual(self.engine.update(frame(0.5, read())),
                         GuidanceAction(ActionKind.CONFIRMED, ean=EAN_A, name="Tomatpure"))

    def test_confirmation_is_said_once_while_the_product_stays_in_view(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))
        for t in (1.0, 1.5, 2.0, 2.5, 3.0):
            self.assertIsNone(self.engine.update(frame(t, read())), t)

    def test_one_read_is_never_enough(self):
        self.assertIsNone(self.engine.update(frame(0.0, read())))
        self.assertIsNone(self.engine.update(frame(0.1)))

    def test_votes_expire_outside_the_confirm_window(self):
        self.engine.update(frame(0.0, read()))
        self.assertIsNone(self.engine.update(frame(2.5, read())))   # 2,5 s > 2,0 s: den första rösten är borta

    def test_product_is_confirmed_again_after_it_has_left_the_view(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))
        self.assertIsNone(self.engine.update(frame(6.0)))           # glömd: >5 s sedan sist
        self.engine.update(frame(7.0, read()))
        self.assertEqual(self.engine.update(frame(7.5, read())).kind, ActionKind.CONFIRMED)

    def test_product_seen_only_now_and_then_is_not_forgotten_or_reconfirmed(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                      # bekräftad
        for t in (4.0, 8.0, 12.0, 16.0):                            # en läsning var 4:e s, nära gränsen
            self.assertIsNone(self.engine.update(frame(t, read(thin=True))), t)

    def test_unknown_product_is_announced_as_unknown_not_by_name(self):
        self.engine.update(frame(0.0, read(EAN_B)))
        action = self.engine.update(frame(0.5, read(EAN_B)))
        self.assertEqual(action, GuidanceAction(ActionKind.UNKNOWN_PRODUCT, ean=EAN_B))

    def test_thin_reads_never_confirm(self):
        for t in (0.0, 0.5, 1.0, 1.5):
            action = self.engine.update(frame(t, read(thin=True)))
            self.assertNotIn(action.kind if action else None, (ActionKind.CONFIRMED, ActionKind.UNKNOWN_PRODUCT))

    def test_two_different_products_far_apart_are_both_confirmed(self):
        both = lambda t: frame(t, read(EAN_A, x=0.2), read(EAN_B, x=0.8))
        actions = [self.engine.update(both(t)) for t in (0.0, 0.5, 1.0)]
        confirmed = {a.ean for a in actions if a}
        self.assertEqual(confirmed, {EAN_A, EAN_B})

    def test_thin_read_after_confirmation_is_silent(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))
        # 2,4 s senare: tidsgränserna (1,8 s mellan beskeden) hindrar inte längre, bara att varan redan är bekräftad
        self.assertIsNone(self.engine.update(frame(2.4, read(thin=True))))


class AimTest(unittest.TestCase):
    def aim(self, x, y):
        return GuidanceEngine(EmptyProductCatalog()).update(frame(0.0, read(x=x, y=y, thin=True)))

    def test_centered_but_unsure_code_asks_for_closer(self):
        self.assertEqual(self.aim(0.5, 0.5).kind, ActionKind.CLOSER)

    def test_inside_the_deadzone_still_asks_for_closer(self):
        self.assertEqual(self.aim(0.62, 0.6).kind, ActionKind.CLOSER)   # dx 0,12 < 0,15, dy 0,10 < 0,25

    def test_code_in_each_edge_says_where_it_is(self):
        self.assertEqual(self.aim(0.10, 0.5).kind, ActionKind.CODE_LEFT)
        self.assertEqual(self.aim(0.90, 0.5).kind, ActionKind.CODE_RIGHT)
        self.assertEqual(self.aim(0.5, 0.05).kind, ActionKind.CODE_ABOVE)
        self.assertEqual(self.aim(0.5, 0.95).kind, ActionKind.CODE_BELOW)

    def test_the_axis_that_is_furthest_out_wins(self):
        # dx = 0,35 (2,3 gånger zonen 0,15), dy = 0,30 (1,2 gånger zonen 0,25)
        self.assertEqual(self.aim(0.85, 0.80).kind, ActionKind.CODE_RIGHT)
        # dx = 0,20 (1,3 gånger zonen), dy = 0,45 (1,8 gånger zonen)
        self.assertEqual(self.aim(0.70, 0.05).kind, ActionKind.CODE_ABOVE)

    def test_the_read_nearest_the_center_is_the_target(self):
        engine = GuidanceEngine(EmptyProductCatalog())
        action = engine.update(frame(0.0, read(x=0.95, y=0.5, thin=True), read(x=0.55, y=0.5, thin=True)))
        self.assertEqual(action.kind, ActionKind.CLOSER)

    def test_invalid_checksum_read_is_guided_like_a_thin_one(self):
        engine = GuidanceEngine(EmptyProductCatalog())
        self.assertEqual(engine.update(frame(0.0, read(None))).kind, ActionKind.CLOSER)

    def test_no_reads_is_silence(self):
        self.assertIsNone(GuidanceEngine(CATALOG).update(frame(0.0)))

    def test_a_reliable_read_waiting_for_its_second_vote_is_not_guided(self):
        engine = GuidanceEngine(CATALOG)
        self.assertIsNone(engine.update(frame(0.0, read(x=0.95, y=0.5))))


class PacingTest(unittest.TestCase):
    def setUp(self):
        self.engine = GuidanceEngine(EmptyProductCatalog())
        self.thin = lambda t, x=0.5: self.engine.update(frame(t, read(x=x, thin=True)))

    def test_same_guidance_is_not_repeated_too_often(self):
        self.assertEqual(self.thin(0.0).kind, ActionKind.CLOSER)
        self.assertIsNone(self.thin(1.0))
        self.assertEqual(self.thin(2.0).kind, ActionKind.CODE_SEEN)   # under repeat_after (3 s): pip i stället
        self.assertEqual(self.thin(3.1).kind, ActionKind.CLOSER)

    def test_two_different_messages_are_kept_apart(self):
        self.assertEqual(self.thin(0.0).kind, ActionKind.CLOSER)
        self.assertIsNone(self.thin(1.0, x=0.1))                               # under min_interval (1,8 s)
        self.assertEqual(self.thin(2.0, x=0.1).kind, ActionKind.CODE_LEFT)

    def test_confirmation_is_not_held_back_by_earlier_guidance(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read(thin=True)))                             # CLOSER
        engine.update(frame(0.2, read()))
        self.assertEqual(engine.update(frame(0.4, read())).kind, ActionKind.CONFIRMED)


class CueTest(unittest.TestCase):
    """Pip när en osäker kod syns men talet hålls tillbaka, så att användaren vet att den syns."""

    def run_thin(self, engine, times, **kw):
        return [(t, a.kind) for t in times for a in [engine.update(frame(t, read(thin=True, **kw)))] if a]

    def test_pips_fill_the_gaps_between_spoken_guidance(self):
        got = self.run_thin(GuidanceEngine(EmptyProductCatalog()), [i * 0.3 for i in range(14)])
        self.assertEqual(got[0], (0.0, ActionKind.CLOSER))
        cues = [t for t, k in got if k is ActionKind.CODE_SEEN]
        self.assertTrue(cues, got)
        self.assertGreaterEqual(min(cues), 1.2)                                   # inte mitt i frasen
        self.assertTrue(all(b - a >= 1.0 - 1e-9 for a, b in zip(cues, cues[1:])), cues)   # högst ett per sekund
        self.assertIn(ActionKind.CLOSER, [k for t, k in got if t >= 3.0])          # pipet sköt inte upp talet

    def test_no_pip_when_nothing_is_seen_or_the_product_is_confirmed(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read()))
        engine.update(frame(0.5, read()))                                          # bekräftad
        for t in (2.0, 3.0, 4.0):
            self.assertIsNone(engine.update(frame(t, read(thin=True))), t)
        self.assertNotIn(ActionKind.CODE_SEEN, kinds(GuidanceEngine(CATALOG).update(frame(t)) for t in (1, 2, 3)))

    def test_no_pip_during_a_conflict(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read(EAN_A)))
        engine.update(frame(0.5, read(EAN_B, x=0.52)))                            # håll stilla
        later = [engine.update(frame(t, read(EAN_A, thin=True))) for t in (2.0, 2.5, 3.0)]
        self.assertNotIn(ActionKind.CODE_SEEN, kinds(later))

    def test_cue_interval_zero_turns_the_pip_off(self):
        got = self.run_thin(GuidanceEngine(EmptyProductCatalog(), GuidanceConfig(cue_interval_s=0)),
                            [i * 0.3 for i in range(14)])
        self.assertNotIn(ActionKind.CODE_SEEN, [k for _, k in got])


class DetailsTest(unittest.TestCase):
    def test_confirmation_carries_the_details_from_the_catalog(self):
        engine = GuidanceEngine(DictProductCatalog({EAN_A: [{"namn": "Tomatpure", "info": ["140 gram"]}]}))
        engine.update(frame(0.0, read()))
        self.assertEqual(engine.update(frame(0.5, read())).details, ("140 gram",))

    def test_details_only_belong_to_a_confirmation(self):
        with self.assertRaises(ValueError):
            GuidanceAction(ActionKind.CLOSER, details=("140 gram",))


class SteadyTest(unittest.TestCase):
    """Elias 6/11: när koden väl är hittad måste man stå still. Säg det om den andra säkra läsningen dröjer."""

    def test_hold_still_when_the_second_reliable_read_is_late(self):
        engine = GuidanceEngine(CATALOG)
        self.assertIsNone(engine.update(frame(0.0, read())))           # första säkra läsningen
        self.assertIsNone(engine.update(frame(0.5)))                   # den andra har inte kommit, men det är tidigt
        self.assertEqual(engine.update(frame(1.0)).kind, ActionKind.STEADY)   # koden tappad: stå still
        self.assertEqual(engine.update(frame(1.5, read())).kind, ActionKind.CONFIRMED)

    def test_no_hold_still_when_the_second_read_comes_in_time(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read()))
        self.assertEqual(engine.update(frame(0.5, read())).kind, ActionKind.CONFIRMED)

    def test_hold_still_is_said_once_and_stops_when_the_vote_expires(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read()))
        said = [engine.update(frame(t)) for t in (1.0, 1.5, 2.0, 2.5, 3.0)]
        self.assertEqual(kinds(said), [ActionKind.STEADY, None, None, None, None])

    def test_steady_after_zero_turns_it_off(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(steady_after_s=0))
        said = [engine.update(frame(0.0, read()))] + [engine.update(frame(t)) for t in (0.5, 1.0, 1.5)]
        self.assertNotIn(ActionKind.STEADY, kinds(said))

    def test_thin_reads_alone_never_ask_to_hold_still(self):
        engine = GuidanceEngine(EmptyProductCatalog())
        said = [engine.update(frame(t, read(thin=True))) for t in (0.0, 1.0, 2.0, 3.0)]
        self.assertNotIn(ActionKind.STEADY, kinds(said))


def seen(t, *centers):
    """En bildruta där detektorn ser koder (mitten 0-1) som inte gick att läsa."""
    return FrameObservation(t, (), tuple(centers))


class SeenCodeTest(unittest.TestCase):
    """Regel 3b (7/11): detektorn ser koden men zxing kan inte läsa den. "Vänd inte varan" (Elias)."""

    def test_a_seen_code_in_the_middle_asks_to_hold_still(self):
        self.assertEqual(GuidanceEngine(CATALOG).update(seen(0.0, (0.5, 0.5))).kind, ActionKind.STEADY)

    def test_a_seen_code_at_the_edge_gives_a_direction(self):
        engine = GuidanceEngine(CATALOG)
        self.assertEqual(engine.update(seen(0.0, (0.5, 0.95))).kind, ActionKind.CODE_BELOW)   # avskuren nertill
        self.assertEqual(GuidanceEngine(CATALOG).update(seen(0.0, (0.05, 0.5))).kind, ActionKind.CODE_LEFT)

    def test_the_seen_code_nearest_the_middle_decides(self):
        action = GuidanceEngine(CATALOG).update(seen(0.0, (0.05, 0.5), (0.55, 0.5)))
        self.assertEqual(action.kind, ActionKind.STEADY)

    def test_a_seen_code_never_confirms_anything(self):
        engine = GuidanceEngine(CATALOG)
        kinds_said = kinds(engine.update(seen(t / 2, (0.5, 0.5))) for t in range(40))
        self.assertNotIn(ActionKind.CONFIRMED, kinds_said)
        self.assertNotIn(ActionKind.UNKNOWN_PRODUCT, kinds_said)

    def test_while_a_code_is_seen_the_no_code_tips_wait(self):
        engine = GuidanceEngine(CATALOG)
        kinds_said = kinds(engine.update(seen(float(t), (0.5, 0.5))) for t in range(20))
        self.assertNotIn(ActionKind.NO_CODE, kinds_said)
        self.assertIn(ActionKind.STEADY, kinds_said)
        self.assertIsNone(engine.update(frame(23.0)))                       # 4 s efter sista synen: vänta (A, 13/11)
        self.assertEqual(engine.update(frame(27.0)).kind, ActionKind.NO_CODE)   # 8 s efter sista synen

    def test_reads_take_precedence_over_what_the_detector_sees(self):
        engine = GuidanceEngine(CATALOG)
        obs = FrameObservation(0.0, (read(thin=True),), ((0.5, 0.5),))
        self.assertEqual(engine.update(obs).kind, ActionKind.CLOSER)   # zxing läste en tunn remsa: som förut

    def test_after_a_successful_scan_a_seen_code_is_ignored(self):
        engine = GuidanceEngine(CATALOG)
        engine.update(frame(0.0, read()))
        engine.update(frame(0.5, read()))                                 # bekräftad
        said = [(t, engine.update(seen(t, (0.5, 0.5)))) for t in (1.0, 3.0, 6.0, 8.0)]
        self.assertTrue(all(a is None for _, a in said), said)            # inget "håll stilla" när varan läggs ned
        self.assertEqual(engine.update(frame(8.5)).kind, ActionKind.READY)   # 8 s efter sista läsningen, som förut

    def test_old_logs_without_detector_behave_as_before(self):
        self.assertEqual(FrameObservation(0.0).seen, ())
        self.assertFalse(FrameObservation(0.0).hand)


def seen_in_hand(t, *centers):
    """Detektorn ser en kod och handmodellen har bekräftat en hand (skannerns ändring 38-39)."""
    return FrameObservation(t, (), tuple(centers), hand=True)


class NextProductTest(unittest.TestCase):
    """9/11: efter "redo för nästa vara" ska en sedd kod i en bekräftad hand starta en ny sökning."""

    def setUp(self, config=None):
        self.engine = GuidanceEngine(CATALOG, config)
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                            # tomatpurén bekräftad

    def ready(self):
        self.assertEqual(self.engine.update(frame(8.5)).kind, ActionKind.READY)
        self.assertIsNone(self.engine.update(frame(12.0)))               # tyst efter "redo", som förut

    def test_a_seen_code_in_a_confirmed_hand_starts_a_new_search(self):
        self.ready()
        self.assertEqual(self.engine.update(seen_in_hand(13.0, (0.5, 0.95))).kind, ActionKind.CODE_BELOW)
        self.assertIsNone(self.engine.update(frame(17.0)))
        self.assertEqual(self.engine.update(frame(21.0)).kind, ActionKind.NO_CODE)   # tipsen är tillbaka, 8 s efter koden
        self.assertEqual(self.engine.update(seen_in_hand(24.0, (0.5, 0.5))).kind, ActionKind.STEADY)

    def test_the_new_product_is_confirmed_as_usual(self):
        self.ready()
        self.engine.update(seen_in_hand(13.0, (0.5, 0.5)))
        self.engine.update(frame(14.0, read(EAN_B)))
        self.assertEqual(self.engine.update(frame(14.5, read(EAN_B))).kind, ActionKind.UNKNOWN_PRODUCT)

    def test_without_a_confirmed_hand_it_stays_silent(self):
        self.setUp(GuidanceConfig(next_after_ready_s=0))                 # bara ändring 39, utan 10/11
        self.ready()
        said = [self.engine.update(seen(t, (0.5, 0.5))) for t in (13.0, 15.0, 20.0, 30.0, 45.0)]
        self.assertEqual(said, [None] * 5)                               # t.ex. en vara på bordet

    def test_before_ready_the_product_just_scanned_does_not_start_a_search(self):
        said = [self.engine.update(seen_in_hand(t, (0.5, 0.5))) for t in (1.0, 3.0, 6.0, 8.0)]
        self.assertEqual(said, [None] * 4)                               # varan är kanske kvar i handen
        self.ready()                                                     # "redo" kommer som förut

    def test_a_hand_without_a_seen_code_starts_nothing(self):
        self.setUp(GuidanceConfig(next_after_ready_s=0))                 # bara ändring 39, utan 10/11
        self.ready()
        empty_hand = [self.engine.update(FrameObservation(t, (), (), hand=True)) for t in (13.0, 20.0, 30.0)]
        self.assertEqual(empty_hand, [None] * 3)

    def test_ready_is_said_again_after_the_next_product(self):
        self.ready()
        self.engine.update(seen_in_hand(13.0, (0.5, 0.5)))
        self.engine.update(frame(14.0, read(EAN_B)))
        self.engine.update(frame(14.5, read(EAN_B)))                      # nästa vara klar
        said = kinds(self.engine.update(seen_in_hand(t, (0.5, 0.5))) for t in (15.0, 17.0, 20.0))
        self.assertEqual(said, [None] * 3)                               # före nästa "redo": ingen ny sökning
        self.assertEqual(self.engine.update(frame(22.5)).kind, ActionKind.READY)


class NextAfterReadyTest(unittest.TestCase):
    """10/11: 5 s efter "redo" utan kod börjar en ny sökning ändå (lampljus: handmodellen 4 %, 45 s tystnad)."""

    def setUp(self, config=None):
        self.engine = GuidanceEngine(CATALOG, config)
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                            # tomatpurén bekräftad
        self.assertEqual(self.engine.update(frame(8.5)).kind, ActionKind.READY)

    def run_empty(self, start, end, step=0.5):
        said, t = [], start
        while t <= end:
            action = self.engine.update(frame(t))
            if action:
                said.append((t, action.kind))
            t += step
        return said

    def test_next_product_after_five_seconds_then_slow_hints(self):
        self.assertEqual(self.run_empty(9.0, 45.0),
                         [(13.5, ActionKind.NEXT_PRODUCT), (23.5, ActionKind.NO_CODE),
                          (33.5, ActionKind.NO_CODE_TURN), (43.5, ActionKind.NO_CODE_FLIP)])

    def test_the_phrase(self):
        from phrases import guidance_text
        self.assertEqual(guidance_text("next_product"), "Håll nästa vara framför dig.")

    def test_zero_keeps_the_old_silence(self):
        self.setUp(GuidanceConfig(next_after_ready_s=0))
        self.assertEqual(self.run_empty(9.0, 90.0), [])

    def test_slow_repeat_zero_says_next_product_once(self):
        self.setUp(GuidanceConfig(no_code_slow_repeat_s=0))
        self.assertEqual(self.run_empty(9.0, 90.0), [(13.5, ActionKind.NEXT_PRODUCT)])

    def test_the_previous_product_glimpsed_postpones_it(self):
        self.assertIsNone(self.engine.update(frame(11.0, read())))     # den skannade varan skymtar förbi
        self.assertEqual(self.run_empty(11.5, 16.0), [(16.0, ActionKind.NEXT_PRODUCT)])   # 5 s efter, inte efter "redo"

    def test_a_seen_code_in_a_hand_before_five_seconds_starts_the_search_as_before(self):
        seen = FrameObservation(10.0, (), ((0.5, 0.5),), hand=True)
        self.assertEqual(self.engine.update(seen).kind, ActionKind.STEADY)   # ändring 39
        self.assertNotIn(ActionKind.NEXT_PRODUCT, [k for _, k in self.run_empty(10.5, 40.0)])

    def test_the_next_product_is_confirmed_as_usual(self):
        self.run_empty(9.0, 14.0)                                         # "håll nästa vara framför dig"
        self.engine.update(frame(15.0, read(EAN_B)))
        self.assertEqual(self.engine.update(frame(15.5, read(EAN_B))).kind, ActionKind.UNKNOWN_PRODUCT)

    def test_it_comes_again_after_the_next_ready(self):
        self.run_empty(9.0, 14.0)
        self.engine.update(frame(15.0, read(EAN_B)))
        self.engine.update(frame(15.5, read(EAN_B)))                      # nästa vara klar
        self.assertEqual(self.run_empty(16.0, 29.0),
                         [(23.5, ActionKind.READY), (28.5, ActionKind.NEXT_PRODUCT)])

    def test_negative_is_an_error(self):
        with self.assertRaises(ValueError):
            GuidanceConfig(next_after_ready_s=-1)


def far(t, hand_m=0.43, *reads, seen=()):
    """En bildruta där handmodellen bekräftat en hand på hand_m meter (skannerns ändring 42)."""
    return FrameObservation(t, tuple(reads), tuple(seen), hand=True, hand_m=hand_m)


class FarHandTest(unittest.TestCase):
    """11/11, regel 4b: ingen kod och den bekräftade handen för långt bort i 2 s: "sakta närmare"."""

    def setUp(self):
        self.engine = GuidanceEngine(CATALOG)

    def speak(self, frames):
        return [(obs.t, a.kind) for obs in frames if (a := self.engine.update(obs))]

    def test_a_hand_far_away_for_two_seconds_gets_closer(self):
        said = self.speak([far(t / 2) for t in range(0, 9)])           # 0-4 s på 0,43 m
        self.assertEqual(said, [(2.0, ActionKind.HAND_FAR)])

    def test_it_repeats_every_six_seconds_and_replaces_the_hints(self):
        said = self.speak([far(t / 2) for t in range(0, 41)])          # 0-20 s
        self.assertEqual(said, [(2.0, ActionKind.HAND_FAR), (8.0, ActionKind.HAND_FAR),
                                (14.0, ActionKind.HAND_FAR), (20.0, ActionKind.HAND_FAR)])

    def test_close_enough_gives_the_usual_hints(self):
        said = self.speak([far(t / 2, 0.31) for t in range(0, 21)])     # 0-10 s på 0,31 m
        self.assertEqual(said, [(4.0, ActionKind.NO_CODE), (10.0, ActionKind.NO_CODE_TURN)])

    def test_the_two_seconds_start_over_when_the_hand_comes_closer(self):
        frames = [far(0.0), far(1.0), far(1.5, 0.30), far(2.0), far(3.0), far(4.0)]
        self.assertEqual(self.speak(frames), [(4.0, ActionKind.HAND_FAR)])   # 2 s efter 2,0, inte efter 0,0

    def test_without_a_confirmed_hand_it_is_as_before(self):
        said = self.speak([FrameObservation(t / 2, hand=False, hand_m=None) for t in range(0, 21)])
        self.assertEqual(said, [(4.0, ActionKind.NO_CODE), (10.0, ActionKind.NO_CODE_TURN)])

    def test_no_pip_while_waiting_to_repeat(self):
        said = self.speak([far(t / 2) for t in range(0, 15)])          # 0-7 s
        self.assertNotIn(ActionKind.CODE_SEEN, [k for _, k in said])

    def test_a_thin_read_still_gets_the_aim_rules(self):
        self.engine.update(far(0.0)); self.engine.update(far(1.0))
        self.assertEqual(self.engine.update(far(2.0, 0.43, read(thin=True))).kind, ActionKind.CLOSER)

    def test_a_reliable_read_waiting_for_its_second_gets_steady(self):
        self.engine.update(far(0.0)); self.engine.update(far(1.0, 0.43, read()))
        self.assertEqual(self.engine.update(far(2.0)).kind, ActionKind.STEADY)   # håll stilla vinner

    def test_it_beats_a_seen_code_because_the_code_is_too_small_there(self):
        self.engine.update(far(0.0)); self.engine.update(far(1.0))
        self.assertEqual(self.engine.update(far(2.0, seen=((0.5, 0.5),))).kind, ActionKind.HAND_FAR)

    def test_not_while_the_product_just_scanned_is_still_in_hand(self):
        self.engine.update(frame(0.0, read())); self.engine.update(frame(0.5, read()))   # bekräftad
        said = self.speak([far(1.0 + t / 2) for t in range(0, 12)])       # 1-6,5 s, före "redo"
        self.assertEqual(said, [])

    def test_after_next_product_it_works_again(self):
        self.engine.update(frame(0.0, read())); self.engine.update(frame(0.5, read()))
        self.assertEqual(self.engine.update(frame(8.5)).kind, ActionKind.READY)
        self.assertEqual(self.engine.update(frame(13.5)).kind, ActionKind.NEXT_PRODUCT)
        said = self.speak([far(14.0 + t / 2) for t in range(0, 7)])       # 14-17 s
        self.assertEqual(said, [(16.0, ActionKind.HAND_FAR)])

    def test_zero_turns_it_off(self):
        self.engine = GuidanceEngine(CATALOG, GuidanceConfig(far_hand_m=0))
        said = self.speak([far(t / 2) for t in range(0, 21)])
        self.assertEqual(said, [(4.0, ActionKind.NO_CODE), (10.0, ActionKind.NO_CODE_TURN)])

    def test_the_phrase(self):
        from phrases import guidance_text
        self.assertEqual(guidance_text("hand_far"), "Sakta närmare.")

    def test_negative_values_are_errors(self):
        for bad in ({"far_hand_m": -0.1}, {"far_hand_s": -1}, {"far_hand_repeat_s": -1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                GuidanceConfig(**bad)

    def test_old_logs_have_no_distance(self):
        self.assertIsNone(FrameObservation(0.0).hand_m)


class AfterACodeTest(unittest.TestCase):
    """13/11, ändring 43. A: efter en kod väntar första tipset 8 s. B: tunn läsning nära ger "håll stilla"."""

    def setUp(self):
        self.engine = GuidanceEngine(CATALOG)

    def speak(self, frames):
        return [(obs.t, a.kind) for obs in frames if (a := self.engine.update(obs))]

    def test_at_the_start_the_first_hint_still_comes_after_four_seconds(self):
        self.assertEqual(self.speak([frame(t / 2) for t in range(0, 9)]), [(4.0, ActionKind.NO_CODE)])

    def test_after_steady_the_hints_wait_eight_seconds_not_four(self):
        # NARA2 14:14:34 "håll stilla", 14:14:37 "håll varan nära": en säker läsning, sedan ingen kod
        said = self.speak([frame(0.0, read())] + [frame(t / 2) for t in range(1, 21)])
        self.assertEqual(said, [(1.0, ActionKind.STEADY), (8.0, ActionKind.NO_CODE)])

    def test_the_rhythm_after_the_first_hint_is_unchanged(self):
        said = self.speak([frame(0.0, read(thin=True))] + [frame(t / 2) for t in range(1, 61)])
        self.assertEqual([t for t, k in said if k in (ActionKind.NO_CODE, ActionKind.NO_CODE_TURN,
                                                       ActionKind.NO_CODE_FLIP)], [8.0, 14.0, 20.0, 30.0])

    def test_equal_values_give_the_old_behaviour(self):
        self.engine = GuidanceEngine(CATALOG, GuidanceConfig(no_code_after_code_s=4.0))
        said = self.speak([frame(0.0, read(thin=True))] + [frame(t / 2) for t in range(1, 11)])
        self.assertEqual([t for t, k in said if k is ActionKind.NO_CODE], [4.0])

    def test_shorter_than_the_start_delay_is_an_error(self):
        with self.assertRaises(ValueError):
            GuidanceConfig(no_code_after_code_s=3.0)

    def test_a_thin_read_close_by_gets_steady_not_closer(self):
        # NARA4 14:22:05: tunn läsning på 0,27 m och 3,0 px/modul gav "sakta närmare"
        obs = FrameObservation(0.0, (CodeRead(EAN_A, (0.5, 0.5), True, distance_m=0.27),))
        self.assertEqual(self.engine.update(obs).kind, ActionKind.STEADY)

    def test_a_thin_read_further_away_still_gets_closer(self):
        obs = FrameObservation(0.0, (CodeRead(EAN_A, (0.5, 0.5), True, distance_m=0.36),))
        self.assertEqual(self.engine.update(obs).kind, ActionKind.CLOSER)

    def test_without_distance_the_hand_is_used_and_without_both_it_is_as_before(self):
        self.assertEqual(self.engine.update(FrameObservation(0.0, (read(thin=True),), hand=True, hand_m=0.28)).kind,
                         ActionKind.STEADY)
        engine = GuidanceEngine(CATALOG)
        self.assertEqual(engine.update(frame(0.0, read(thin=True))).kind, ActionKind.CLOSER)

    def test_a_code_at_the_edge_still_gets_a_direction_when_close(self):
        obs = FrameObservation(0.0, (CodeRead(EAN_A, (0.5, 0.95), True, distance_m=0.27),))
        self.assertEqual(self.engine.update(obs).kind, ActionKind.CODE_BELOW)

    def test_steady_close_by_still_pips_when_held_back(self):
        close = lambda t: FrameObservation(t, (CodeRead(EAN_A, (0.5, 0.5), True, distance_m=0.27),))
        said = [a.kind if a else None for a in (self.engine.update(close(t)) for t in (0.0, 1.0, 2.5))]
        self.assertEqual(said, [ActionKind.STEADY, None, ActionKind.CODE_SEEN])

    def test_near_enough_zero_turns_b_off(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(near_enough_m=0))
        obs = FrameObservation(0.0, (CodeRead(EAN_A, (0.5, 0.5), True, distance_m=0.27),))
        self.assertEqual(engine.update(obs).kind, ActionKind.CLOSER)


class ConflictTest(unittest.TestCase):
    def setUp(self):
        self.engine = GuidanceEngine(CATALOG)

    def conflict(self, t0=0.0):
        self.engine.update(frame(t0, read(EAN_A, x=0.5)))
        return self.engine.update(frame(t0 + 0.5, read(EAN_B, x=0.52)))

    def test_two_different_codes_from_the_same_place_say_hold_still(self):
        self.assertEqual(self.conflict().kind, ActionKind.HOLD_STILL)

    def test_nothing_is_confirmed_during_and_after_a_conflict(self):
        self.conflict()
        results = [self.engine.update(frame(t, read(EAN_A, x=0.5))) for t in (1.0, 1.5, 2.0, 2.5)]
        self.assertTrue(all(r is None for r in results), results)

    def test_the_product_is_confirmed_once_the_conflict_has_cooled_down(self):
        self.conflict()
        self.engine.update(frame(1.0, read(EAN_A)))
        self.engine.update(frame(1.5, read(EAN_A)))
        self.engine.update(frame(8.0, read(EAN_A)))
        self.assertEqual(self.engine.update(frame(8.5, read(EAN_A))).kind, ActionKind.CONFIRMED)

    def alternating(self, engine, start, seconds, step=0.5):
        """Rätt och fel kod om vartannat från samma ställe, som kaffefiltret 29/10."""
        actions = []
        for i in range(int(seconds / step)):
            ean = EAN_A if i % 2 == 0 else EAN_B
            actions.append(engine.update(frame(start + i * step, read(ean, x=0.5))))
        return [a for a in actions if a]

    def test_a_conflict_that_does_not_clear_escalates_from_hold_still_to_closer(self):
        kinds = [a.kind for a in self.alternating(self.engine, 0.0, 15.0)]
        first_closer = kinds.index(ActionKind.CLOSER)
        self.assertEqual(kinds[0], ActionKind.HOLD_STILL)
        self.assertTrue(all(k is ActionKind.HOLD_STILL for k in kinds[:first_closer]))
        self.assertTrue(all(k is ActionKind.CLOSER for k in kinds[first_closer:]))   # och tillbaka till håll stilla gör den inte

    def test_a_new_conflict_after_a_quiet_spell_starts_with_hold_still_again(self):
        self.alternating(self.engine, 0.0, 15.0)
        self.assertEqual(self.alternating(self.engine, 40.0, 2.0)[0].kind, ActionKind.HOLD_STILL)

    def test_codes_in_different_places_are_not_a_conflict(self):
        self.engine.update(frame(0.0, read(EAN_A, x=0.2)))
        self.assertIsNone(self.engine.update(frame(0.5, read(EAN_B, x=0.8))))

    def test_old_reads_do_not_conflict(self):
        self.engine.update(frame(0.0, read(EAN_A)))
        self.assertIsNone(self.engine.update(frame(4.0, read(EAN_B, x=0.52))))   # 4 s > 3 s: A är glömd

    def test_a_stray_read_after_confirmation_does_not_interrupt_the_user(self):
        self.engine.update(frame(0.0, read(EAN_A)))
        self.engine.update(frame(0.5, read(EAN_A)))                              # bekräftad
        self.assertIsNone(self.engine.update(frame(1.0, read(EAN_B, x=0.52, thin=True))))

    def test_thin_reads_can_be_kept_out_of_conflicts(self):
        # Köksprovet 4/11: en tunn felläsning bredvid tomatpurén gav "håll stilla" och 4 s extra väntan.
        thin_wrong = lambda engine: engine.update(frame(0.5, read(EAN_B, x=0.52, thin=True)))
        strict = GuidanceEngine(CATALOG, GuidanceConfig(conflict_from_thin=True))
        strict.update(frame(0.0, read(EAN_A)))
        self.assertEqual(thin_wrong(strict).kind, ActionKind.HOLD_STILL)
        relaxed = GuidanceEngine(CATALOG)   # standard sedan replay 5/11
        relaxed.update(frame(0.0, read(EAN_A)))
        thin_wrong(relaxed)
        self.assertEqual(relaxed.update(frame(1.0, read(EAN_A))).kind, ActionKind.CONFIRMED)

    def test_reliable_reads_still_conflict_when_thin_ones_are_kept_out(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(conflict_from_thin=False))
        engine.update(frame(0.0, read(EAN_A)))
        self.assertEqual(engine.update(frame(0.5, read(EAN_B, x=0.52))).kind, ActionKind.HOLD_STILL)

    def test_votes_collected_before_a_conflict_do_not_count_afterwards(self):
        # Långt röstfönster, så att gamla röster annars skulle överleva konflikten.
        engine = GuidanceEngine(CATALOG, GuidanceConfig(confirm_reads=3, confirm_window_s=10.0))
        engine.update(frame(0.0, read(EAN_A)))
        engine.update(frame(0.5, read(EAN_A)))                                    # 2 av 3 röster
        self.assertEqual(engine.update(frame(0.7, read(EAN_B, x=0.52))).kind, ActionKind.HOLD_STILL)
        self.assertIsNone(engine.update(frame(8.0, read(EAN_A))))                 # skulle ha varit röst 3


class NoCodeTest(unittest.TestCase):
    def setUp(self):
        self.engine = GuidanceEngine(CATALOG)

    def run_empty(self, start, end, step=0.5):
        """Bildrutor utan kod. Returnerar (tid, slag) för varje besked."""
        said = []
        t = start
        while t <= end:
            action = self.engine.update(frame(t))
            if action:
                said.append((t, action.kind))
            t += step
        return said

    def test_hints_come_in_turn_first_every_six_then_every_ten_seconds_without_end(self):
        N, TURN, FLIP = ActionKind.NO_CODE, ActionKind.NO_CODE_TURN, ActionKind.NO_CODE_FLIP
        self.assertEqual(self.run_empty(0.0, 60.0),
                         [(4.0, N), (10.0, TURN), (16.0, FLIP), (26.0, N), (36.0, TURN), (46.0, FLIP), (56.0, N)])

    def test_slow_repeat_zero_stops_after_the_fast_hints(self):
        self.engine = GuidanceEngine(CATALOG, GuidanceConfig(no_code_slow_repeat_s=0))
        self.assertEqual([t for t, _ in self.run_empty(0.0, 60.0)], [4.0, 10.0, 16.0])

    def test_without_fast_hints_the_slow_ones_start_at_the_first_delay(self):
        self.engine = GuidanceEngine(CATALOG, GuidanceConfig(no_code_fast=0))
        self.assertEqual([t for t, _ in self.run_empty(0.0, 30.0)], [4.0, 14.0, 24.0])

    def test_a_code_starts_a_new_search(self):
        self.run_empty(0.0, 30.0)                                   # tre gånger, sedan tyst
        self.assertEqual(self.engine.update(frame(31.0, read(thin=True))).kind, ActionKind.CLOSER)
        self.assertEqual(self.run_empty(31.5, 40.0), [(39.0, ActionKind.NO_CODE)])   # 8 s efter koden (A, 13/11)

    def test_after_a_successful_scan_it_says_ready_once_instead_of_no_code(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                      # bekräftad
        self.engine.update(frame(1.0, read()))                      # varan syns fortfarande en stund
        N, TURN, FLIP = ActionKind.NO_CODE, ActionKind.NO_CODE_TURN, ActionKind.NO_CODE_FLIP
        self.assertEqual(self.run_empty(1.5, 90.0),
                         [(9.0, ActionKind.READY),                  # 8 s efter sista läsningen
                          (14.0, ActionKind.NEXT_PRODUCT),          # 10/11: 5 s efter "redo", sedan glesa tips
                          (24.0, N), (34.0, TURN), (44.0, FLIP), (54.0, N), (64.0, TURN), (74.0, FLIP), (84.0, N)])

    def test_ready_waits_while_the_confirmed_product_is_still_in_view(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))
        for t in range(1, 30):                                      # varan ligger kvar i bild
            self.assertIsNone(self.engine.update(frame(float(t), read())), t)

    def test_a_new_code_before_ready_cancels_it(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))
        self.engine.update(frame(5.0, read(EAN_B, thin=True)))      # nästa vara dyker upp innan "redo"
        said = self.run_empty(5.5, 40.0)
        self.assertNotIn(ActionKind.READY, [k for _, k in said])
        self.assertEqual(said, [(13.0, ActionKind.NO_CODE), (19.0, ActionKind.NO_CODE_TURN),   # 8 s efter koden
                                (25.0, ActionKind.NO_CODE_FLIP), (35.0, ActionKind.NO_CODE)])

    def test_the_same_product_glimpsed_after_it_was_forgotten_does_not_restart_the_hints(self):
        # Provet 5/11: tomatpurén bekräftad, borta i över 5 s, en enda läsning till, sedan "hittar ingen streckkod".
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                      # bekräftad
        self.assertIsNone(self.engine.update(frame(7.0, read())))   # glömd (>5 s), skymtar förbi en gång
        self.assertEqual(self.run_empty(7.5, 40.0),
                         [(15.0, ActionKind.READY),                 # 8 s efter, inga tips före "redo"
                          (20.0, ActionKind.NEXT_PRODUCT), (30.0, ActionKind.NO_CODE), (40.0, ActionKind.NO_CODE_TURN)])

    def test_the_previous_product_counts_as_a_new_code_once_a_new_search_has_begun(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                      # tomatpurén bekräftad
        self.engine.update(frame(10.0, read(EAN_B, thin=True)))     # ny sökning: en annan vara
        self.run_empty(10.5, 20.5)                                  # tips 1 och 2
        self.engine.update(frame(21.0, read(EAN_A, thin=True)))     # tomatpurén igen, mitt i sökningen
        self.assertEqual(self.run_empty(21.5, 30.0)[0], (29.0, ActionKind.NO_CODE))   # tipsen börjar om, 8 s efter koden

    def test_ready_after_zero_never_says_ready(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(ready_after_s=0))
        engine.update(frame(0.0, read()))
        engine.update(frame(0.5, read()))
        self.assertTrue(all(engine.update(frame(float(t))) is None for t in range(1, 60)))

    def test_a_new_product_after_a_successful_scan_rearms_the_prompt(self):
        self.engine.update(frame(0.0, read()))
        self.engine.update(frame(0.5, read()))                      # tomatpurén bekräftad
        self.engine.update(frame(20.0, read(EAN_B, thin=True)))     # en annan vara dyker upp, osäker
        self.assertEqual(self.run_empty(20.5, 34.0), [(28.0, ActionKind.NO_CODE), (34.0, ActionKind.NO_CODE_TURN)])

    def test_zero_disables_the_hints(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(no_code_fast=0, no_code_slow_repeat_s=0))
        self.assertTrue(all(engine.update(frame(t)) is None for t in range(0, 60)))


class ConfigTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(GuidanceConfig().confirm_reads, 2)

    def test_invalid_values_are_rejected(self):
        for bad in ({"confirm_reads": 0}, {"confirm_window_s": 0}, {"min_interval_s": -1}, {"conflict_escalate_s": 0},
                    {"no_code_after_s": 0}, {"no_code_repeat_s": -1}, {"no_code_fast": -1}, {"no_code_slow_repeat_s": -1}, {"cue_interval_s": -1}, {"ready_after_s": -1}, {"steady_after_s": -0.5}, {"cue_quiet_s": -0.1},
                    {"deadzone_x": 0}, {"deadzone_y": 0.6}, {"conflict_radius": 0}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    GuidanceConfig(**bad)

    def test_a_single_vote_config_confirms_immediately(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(confirm_reads=1))
        self.assertEqual(engine.update(frame(0.0, read())).kind, ActionKind.CONFIRMED)


if __name__ == "__main__":
    unittest.main()
