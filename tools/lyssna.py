# ===================== NY FIL AV CLAUDE (2026-11-13) =====================
# Lyssna på fraser med samma röst och hastighet som systemet (Piper, tts_engine.py), utan att starta
# kameran eller skannern. Elias 13/11: provlyssna på formuleringar innan de byggs in.
#   python3 tools/lyssna.py "Senaste varan var Tomatpure, 500 gram." "Du har två varor i korgen."
#   python3 tools/lyssna.py --knappar      alla svar från tools/knappar.py, med två exempelvaror
#   python3 tools/lyssna.py --fraser       alla fasta vägledningsfraser (phrases.py)
# Fraserna sparas i cache/tts/ som vanligt. Kör inte samtidigt som skannern (Piper delar kärnor).
# =========================================================================
import argparse
import os
import subprocess
import sys
import time
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)   # projektets rot

from tools.knappar import ButtonState   # noqa: E402


def button_phrases() -> List[str]:
    """Knapparnas svar, i den ordning de oftast hörs: före skanning, efter en vara, efter två."""
    state = ButtonState()
    phrases = [state.answer("help"), state.answer("last"), state.answer("basket"), state.answer("repeat")]
    state.on_event({"type": "guidance", "action": "confirmed", "ean": "1", "name": "Tomatpure",
                    "details": ["500 gram"], "basket": "added", "text": "Tomatpure. 500 gram. Tillagd."})
    phrases += [state.answer("last"), state.answer("basket")]
    state.on_event({"type": "guidance", "action": "confirmed", "ean": "2", "name": "Linser",
                    "details": [], "basket": "added", "text": "Linser. Tillagd."})
    phrases += [state.answer("basket")]
    return list(dict.fromkeys(phrases))   # utan dubbletter, ordningen kvar


def main() -> int:
    ap = argparse.ArgumentParser(description="Lyssna på fraser med systemets röst, utan kameran")
    ap.add_argument("text", nargs="*", help="fraser att läsa upp, en per argument")
    ap.add_argument("--knappar", action="store_true", help="knapparnas svar (tools/knappar.py)")
    ap.add_argument("--fraser", action="store_true", help="alla fasta vägledningsfraser (phrases.py)")
    ap.add_argument("--paus", type=float, default=0.6, help="sekunder mellan fraserna")
    args = ap.parse_args()
    phrases = list(args.text)
    if args.knappar:
        phrases += button_phrases()
    if args.fraser:
        from phrases import guidance_phrases
        phrases += guidance_phrases()
    if not phrases:
        ap.print_help()
        return 1
    os.chdir(ROOT)   # Piper och röstmodellen ligger relativt projektets rot
    from tts_engine import TTSEngine
    engine = TTSEngine()
    try:
        for text in phrases:
            path, cached, temporary = engine.get_wav(text)
            if path is None:
                print(f"❌ Talsyntesen misslyckades: {text!r}")
                continue
            print(f"🔊 {text}" + ("" if cached else "   (ny, genererad nu)"))
            subprocess.run(["pw-play", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(args.paus)
    except KeyboardInterrupt:
        print("\nAvbrutet.")
    finally:
        stop = getattr(engine, "_stop_proc", None)
        if stop:
            stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
