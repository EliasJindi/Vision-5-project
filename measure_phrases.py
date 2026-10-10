# ===================== NY FIL AV CLAUDE (2026-10-10) =====================
# Mätverktyg: jämför fraslängd för olika formuleringar/talhastigheter.
# Påverkar inte systemet; körs separat.
# =========================================================================
"""
measure_phrases.py - Jämför hur långa akutfraserna blir i olika varianter.

Användning (från ~/ai_glasses, med venv aktiv):
    python3 measure_phrases.py           # bara siffror
    python3 measure_phrases.py --play    # spelar även upp varje variant

Mäter också vinsten med att hålla Piper igång jämfört med att starta den per fras.
Resultatet sparas i logs/phrase_measurement_<tid>.txt (underlag till rapporten).
"""
import os
import subprocess
import sys
import time

from tts_engine import TTSEngine, wav_duration
from phrases import format_phrase

SAMPLES = [("bil", 0.6), ("person", 0.8), ("lastbil", 2.4)]

# (namn, avståndsstil, length_scale, sentence_silence)
VARIANTS = [
    ("A  nuvarande",            "decimal", 1.0,  0.2),
    ("B  halvmetrar",           "half",    1.0,  0.2),
    ("C  utan 'meter'",         "nounit",  1.0,  0.2),
    ("D  komma i st f punkt",   "comma",   1.0,  0.2),
    ("E  nuvarande, kort paus", "decimal", 1.0,  0.05),
    ("F  nuvarande, snabbare",  "decimal", 0.85, 0.2),
    ("G  komma + snabbare",     "comma",   0.85, 0.05),
]


def main():
    play = "--play" in sys.argv
    out_dir = "/tmp/phrase_test"
    os.makedirs(out_dir, exist_ok=True)
    lines = []

    def report(s=""):
        print(s)
        lines.append(s)

    # 1. Gamla sättet (ny Piper per fras) mot Piper som redan är igång
    engine = TTSEngine()
    text = format_phrase("bil", 0.6, "decimal")
    t0 = time.time()
    engine._synth_oneshot(text, f"{out_dir}/oneshot.wav", 15)
    oneshot = time.time() - t0
    engine.synthesize("Start.", f"{out_dir}/warm.wav")  # laddar modellen
    t0 = time.time()
    persistent_ok = engine._synth_persistent(text, f"{out_dir}/persistent.wav", 10)
    persistent = time.time() - t0
    report("== Syntes av en fras ==")
    report(f"Ny Piper per fras (gamla sättet): {oneshot:.2f} s")
    if persistent_ok:
        report(f"Piper redan igång:                {persistent:.2f} s")
    else:
        report("Piper redan igång:                MISSLYCKADES (json-input stöds inte?) -> reserv används")
    report("Från cache:                       ~0,00 s (filen finns redan)\n")

    # 2. Hur långa blir fraserna?
    report("== Längd på uppläst fras (sekunder) ==")
    header = f"{'Variant':<26}" + "".join(f"{format_phrase(l, d, 'decimal'):>22}" for l, d in SAMPLES) + "   snitt"
    report(header)
    for name, style, ls, ss in VARIANTS:
        eng = TTSEngine(length_scale=ls, sentence_silence=ss)
        durs, files = [], []
        for label, dist in SAMPLES:
            phrase = format_phrase(label, dist, style)
            path = f"{out_dir}/{name[0]}_{label}.wav"
            if eng.synthesize(phrase, path):
                durs.append(wav_duration(path))
                files.append((phrase, path))
            else:
                durs.append(None)
        cells = "".join(f"{(f'{d:.2f}' if d else 'fel'):>22}" for d in durs)
        ok = [d for d in durs if d]
        report(f"{name:<26}{cells}   {sum(ok) / len(ok):.2f}" if ok else f"{name:<26}{cells}")
        eng._stop_proc()
        if play:
            for phrase, path in files:
                print(f"   ▶ {name}: {phrase}")
                subprocess.run(["pw-play", path])
                time.sleep(0.4)

    report("\nExempelfraser:")
    for name, style, _, _ in VARIANTS[:4]:
        report(f"  {name}: " + " | ".join(format_phrase(l, d, style) for l, d in SAMPLES))

    os.makedirs("logs", exist_ok=True)
    path = f"logs/phrase_measurement_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSparat: {path}")


if __name__ == "__main__":
    main()
