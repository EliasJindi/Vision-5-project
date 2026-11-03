import unittest

from voice_guidance import (ActionKind, DictProductCatalog, EmptyProductCatalog, GuidanceAction,
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
        self.assertIsNone(self.engine.update(frame(5.0)))           # glömd: >2 s sedan sist
        self.engine.update(frame(6.0, read()))
        self.assertEqual(self.engine.update(frame(6.5, read())).kind, ActionKind.CONFIRMED)

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
        self.assertEqual(self.aim(0.65, 0.6).kind, ActionKind.CLOSER)

    def test_code_in_each_edge_says_where_it_is(self):
        self.assertEqual(self.aim(0.10, 0.5).kind, ActionKind.CODE_LEFT)
        self.assertEqual(self.aim(0.90, 0.5).kind, ActionKind.CODE_RIGHT)
        self.assertEqual(self.aim(0.5, 0.05).kind, ActionKind.CODE_ABOVE)
        self.assertEqual(self.aim(0.5, 0.95).kind, ActionKind.CODE_BELOW)

    def test_the_axis_that_is_furthest_out_wins(self):
        # dx = 0,35 (1,75 gånger zonen), dy = 0,30 (1,2 gånger zonen)
        self.assertEqual(self.aim(0.85, 0.80).kind, ActionKind.CODE_RIGHT)
        # dx = 0,25 (1,25 gånger zonen), dy = 0,40 (1,6 gånger zonen)
        self.assertEqual(self.aim(0.75, 0.10).kind, ActionKind.CODE_ABOVE)

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
        self.assertIsNone(self.thin(2.0))     # över min_interval men under repeat_after (3 s)
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

    def test_votes_collected_before_a_conflict_do_not_count_afterwards(self):
        # Långt röstfönster, så att gamla röster annars skulle överleva konflikten.
        engine = GuidanceEngine(CATALOG, GuidanceConfig(confirm_reads=3, confirm_window_s=10.0))
        engine.update(frame(0.0, read(EAN_A)))
        engine.update(frame(0.5, read(EAN_A)))                                    # 2 av 3 röster
        self.assertEqual(engine.update(frame(0.7, read(EAN_B, x=0.52))).kind, ActionKind.HOLD_STILL)
        self.assertIsNone(engine.update(frame(8.0, read(EAN_A))))                 # skulle ha varit röst 3


class ConfigTest(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(GuidanceConfig().confirm_reads, 2)

    def test_invalid_values_are_rejected(self):
        for bad in ({"confirm_reads": 0}, {"confirm_window_s": 0}, {"min_interval_s": -1},
                    {"deadzone_x": 0}, {"deadzone_y": 0.6}, {"conflict_radius": 0}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    GuidanceConfig(**bad)

    def test_a_single_vote_config_confirms_immediately(self):
        engine = GuidanceEngine(CATALOG, GuidanceConfig(confirm_reads=1))
        self.assertEqual(engine.update(frame(0.0, read())).kind, ActionKind.CONFIRMED)


if __name__ == "__main__":
    unittest.main()
