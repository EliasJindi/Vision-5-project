# ===================== NY FIL AV CLAUDE (2026-11-13) =====================
# tools/lyssna.py: vilka fraser --knappar spelar. Själva uppspelningen kräver Piper och pw-play (Pi:n).
# =========================================================================
import unittest

from tools.lyssna import button_phrases


class ButtonPhrasesTest(unittest.TestCase):
    def test_the_button_answers_in_the_order_they_are_heard(self):
        self.assertEqual(button_phrases(), [
            "Mellanslag, hör igen. Ess, senaste varan. Kå, korgen. Hå, hjälp.",
            "Ingen vara är skannad än.",
            "Korgen är tom.",
            "Inget att upprepa än.",
            "Senaste varan var Tomatpure, 500 gram.",
            "Du har Tomatpure i korgen.",
            "Du har två varor i korgen, Tomatpure och Linser.",
        ])


if __name__ == "__main__":
    unittest.main()
