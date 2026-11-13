# ===================== NY FIL AV CLAUDE (2026-11-13) =====================
# tools/knappar.py: svaren på tangenterna och hela vägen genom den riktiga länken (TcpJsonLink).
# =========================================================================
import selectors
import threading
import unittest

from tools import knappar
from tools.knappar import ButtonState, LinkClient, basket_text, handle_key
from voice_guidance import TcpJsonLink
from voice_guidance.link import MAX_SAY_CHARS


def confirmed(ean, name, details=(), basket="added"):
    return {"type": "guidance", "action": "confirmed", "ean": ean, "name": name, "details": list(details),
            "basket": basket, "text": f"{name}. Tillagd."}


class AnswerTest(unittest.TestCase):
    def setUp(self):
        self.state = ButtonState()

    def test_before_anything_has_happened(self):
        self.assertEqual(self.state.answer("repeat"), "Inget att upprepa än.")
        self.assertEqual(self.state.answer("last"), "Ingen vara är skannad än.")
        self.assertEqual(self.state.answer("basket"), "Korgen är tom.")

    def test_repeat_gives_the_last_spoken_text_but_never_the_pip(self):
        self.state.on_event({"type": "guidance", "action": "closer", "text": "Sakta närmare."})
        self.state.on_event({"type": "guidance", "action": "code_seen", "text": "♪"})
        self.assertEqual(self.state.answer("repeat"), "Sakta närmare.")

    def test_reads_and_other_events_change_nothing(self):
        self.state.on_event({"type": "read", "ean": "7340083497834", "text": "x"})
        self.state.on_event({"type": "hello", "protocol": 1})
        self.assertEqual(self.state.answer("repeat"), "Inget att upprepa än.")

    def test_last_product_with_details(self):
        self.state.on_event(confirmed("7340083497834", "Tomatpure", ["500 gram"]))
        self.assertEqual(self.state.answer("last"), "Senaste varan var Tomatpure, 500 gram.")

    def test_last_product_unknown(self):
        self.state.on_event({"type": "guidance", "action": "unknown_product", "ean": "7331642037042",
                             "name": None, "text": "Okänd vara."})
        self.assertEqual(self.state.answer("last"), "Senaste varan var en okänd vara.")
        self.assertEqual(self.state.answer("basket"), "Korgen är tom.")             # okända varor läggs aldrig i korgen

    def test_basket_counts_each_product_once(self):
        self.state.on_event(confirmed("1", "Tomatpure"))
        self.state.on_event(confirmed("2", "Linser"))
        self.state.on_event(confirmed("1", "Tomatpure", basket="already"))          # "finns redan i korgen"
        self.assertEqual(self.state.answer("basket"), "Du har två varor i korgen, Tomatpure och Linser.")

    def test_basket_wording(self):
        self.assertEqual(basket_text(["Tomatpure"]), "Du har Tomatpure i korgen.")
        self.assertEqual(basket_text(["A", "B", "C"]), "Du har tre varor i korgen, A, B och C.")
        self.assertTrue(basket_text([f"V{i}" for i in range(12)]).startswith("Du har 12 varor i korgen, "))

    def test_no_colons_and_no_lone_letters(self):
        # 13/11: kolon och ensamma bokstäver lät konstigt uppläst
        self.state.on_event(confirmed("1", "Tomatpure", ["500 gram"]))
        self.state.on_event(confirmed("2", "Linser"))
        for what in ("last", "basket", "help", "repeat"):
            with self.subTest(what=what):
                self.assertNotIn(":", self.state.answer(what))
        self.assertEqual(self.state.answer("help"), "Mellanslag, hör igen. Ess, senaste varan. Kå, korgen. Hå, hjälp.")

    def test_a_long_basket_always_fits_the_link(self):
        names = [f"Ekologisk krossad tomat {i}" for i in range(15)]
        text = basket_text(names)
        self.assertLessEqual(len(text), MAX_SAY_CHARS)
        self.assertTrue(text.startswith("Du har 15 varor i korgen, Ekologisk krossad tomat 0"), text)
        self.assertIn("till.", text)

    def test_help_fits_the_link(self):
        self.assertLessEqual(len(self.state.answer("help")), MAX_SAY_CHARS)

    def test_an_unknown_question_is_an_error(self):
        with self.assertRaises(ValueError):
            self.state.answer("weather")


class ThroughTheLinkTest(unittest.TestCase):
    """Den riktiga länken med en låtsad skanner: besked ut, tangent in, svaret når rösten."""

    def setUp(self):
        self.said = []
        self.got = threading.Event()

        def on_say(command):
            self.said.append(command.text)
            self.got.set()
        self.link = TcpJsonLink(port=0, on_say=on_say)
        self.client = LinkClient(port=self.link.start())
        self.state = ButtonState()

    def tearDown(self):
        self.client.close()
        self.link.close()

    def pump(self, until):
        sel = selectors.DefaultSelector()
        sel.register(self.client.sock, selectors.EVENT_READ)
        for _ in range(50):
            if until():
                return
            if sel.select(timeout=0.1):
                for event in self.client.receive() or []:
                    self.state.on_event(event)
        self.fail("händelsen kom aldrig fram")

    def press(self, key):
        self.got.clear()
        text = handle_key(self.client, self.state, key)
        self.assertTrue(self.got.wait(3.0), "rösten fick inget")
        return text

    def test_keys_reach_the_voice(self):
        self.pump(lambda: self.link._clients)                                       # klienten är ansluten
        self.link.publish(confirmed("7340083497834", "Tomatpure", ["500 gram"]))
        self.pump(lambda: self.state.last_product)
        self.assertEqual(self.press("K"), "Du har Tomatpure i korgen.")
        self.assertEqual(self.press("s"), "Senaste varan var Tomatpure, 500 gram.")
        self.assertEqual(self.press(" "), "Tomatpure. Tillagd.")
        self.assertEqual(self.said, ["Du har Tomatpure i korgen.", "Senaste varan var Tomatpure, 500 gram.",
                                     "Tomatpure. Tillagd."])

    def test_other_keys_send_nothing(self):
        self.assertIsNone(handle_key(self.client, self.state, "x"))
        self.assertEqual(self.said, [])


class ConnectTest(unittest.TestCase):
    def test_without_a_scanner_it_says_what_to_do(self):
        import contextlib
        import io
        import socket
        import sys
        from unittest import mock
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            free = s.getsockname()[1]                                               # stängd port: ingen lyssnar
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["knappar.py", "--port", str(free)]), contextlib.redirect_stdout(out):
            self.assertEqual(knappar.main(), 1)
        self.assertIn(f"--lank {free}", out.getvalue())


if __name__ == "__main__":
    unittest.main()
