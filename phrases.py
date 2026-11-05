# ===================== NY FIL AV CLAUDE (2026-10-10) =====================
# All formulering av varningar på ett ställe. DISTANCE_STYLE = "comma" (variant G)
# valdes efter measure_phrases.py. EMERGENCY_LABELS används av filtret och cachen.
# 2026-11-03: fraserna för röstvägledningen (voice_guidance/) ligger här också.
# =========================================================================
"""
phrases.py - Exakt hur varningar formuleras. Används av detect_spatial.py
och measure_phrases.py, och för att förgenerera cachen, så att allt matchar.
"""

# Hur avstånd uttalas. Mät varianterna med: python3 measure_phrases.py
#   "decimal": "Bil. 0,6 meter."      "comma": "Bil, 0,6 meter."
#   "half":    "Bil. En halv meter."  "nounit": "Bil, 0,6."
# Vald efter measure_phrases.py 2026-10-10: variant G ("Bil, 0,6 meter." + snabbare tal och
# kort paus i tts_engine.py) gav 2,05 s mot 2,93 s för "Bil. 0,6 meter." och var lätt att förstå.
DISTANCE_STYLE = "comma"

_HALF_WORDS = {0.5: "en halv meter", 1.0: "en meter", 1.5: "en och en halv meter",
               2.0: "två meter", 2.5: "två och en halv meter", 3.0: "tre meter"}


def format_phrase(label, distance, style=DISTANCE_STYLE):
    """Den exakta frasen som läses upp. Samma funktion används för cachen, så de matchar alltid."""
    name = label.capitalize()
    dec = f"{distance:.1f}".replace('.', ',')
    if style == "comma":
        return f"{name}, {dec} meter."
    if style == "nounit":
        return f"{name}, {dec}."
    if style == "half":
        half = max(0.5, round(distance * 2) / 2)
        words = _HALF_WORDS.get(half, f"{half:g} meter".replace('.', ','))
        return f"{name}. {words[0].upper() + words[1:]}."
    return f"{name}. {dec} meter."


# ---------- Röstvägledning (voice_guidance/) ----------
# Nycklarna är voice_guidance.model.ActionKind.value. Korta fraser: varje ord kostar tid.
GUIDANCE_PHRASES = {
    "closer": "Lite närmare.",
    "hold_still": "Håll stilla.",
    "unknown_product": "Okänd vara.",
    # Ingen kod syns: tre tips i tur och ordning, sedan om igen. Elias 5/11: rösten ska blanda sig i mer,
    # och kommandona ska vara korta och enkla, eftersom användaren inte ser. Avstånd i armlängd, inte cm.
    "no_code": "Håll varan framför dig, en halv armlängd bort.",   # läsningarna 4-5/11 kom på 18-45 cm
    "no_code_turn": "Vrid varan sakta.",
    "no_code_flip": "Vänd varan upp och ner.",                    # koden sitter ofta på botten
    "ready": "Redo för nästa vara.",
}
# Efter namnet, när varan lagts i korgen (voice_guidance/basket.py). Elias 5/11.
BASKET_PHRASES = {
    "added": "Tillagd.",
    "already": "Finns redan i korgen.",
}
# Riktning. Motorn säger var koden ligger i bilden, konventionen avgör orden:
#   head: användaren vrider huvudet mot koden.  hand: användaren flyttar varan mot bildens mitt.
AIM_PHRASES = {
    "head": {"code_left": "Lite åt vänster.", "code_right": "Lite åt höger.",
             "code_above": "Lite uppåt.", "code_below": "Lite nedåt."},
    "hand": {"code_left": "Lite åt höger.", "code_right": "Lite åt vänster.",
             "code_above": "Lite nedåt.", "code_below": "Lite uppåt."},
}


def _sentence(text):
    text = text.strip()
    return f"{text[:1].upper()}{text[1:]}" + ("" if text[-1:] in ".!?" else ".")


def guidance_text(kind, convention="head", name=None, details=(), basket=None):
    """
    Frasen för ett vägledningsbesked. 'confirmed' kräver ett varunamn. details läses efter namnet,
    och basket ('added'/'already') sist: "Tomatpure. 500 gram. Tillagd."
    """
    if kind == "confirmed":
        if not name:
            raise ValueError("'confirmed' kräver ett varunamn")
        parts = [_sentence(part) for part in (name, *details)]
        if basket is not None:
            parts.append(BASKET_PHRASES[basket])
        return " ".join(parts)
    if basket is not None:
        raise ValueError("basket hör bara till 'confirmed'")
    if kind in GUIDANCE_PHRASES:
        return GUIDANCE_PHRASES[kind]
    try:
        return AIM_PHRASES[convention][kind]
    except KeyError:
        raise ValueError(f"okänt vägledningsbesked {kind!r} med konvention {convention!r}") from None


def guidance_phrases():
    """Alla fasta vägledningsfraser (båda konventionerna). Varunamn genereras när de behövs."""
    phrases = set(GUIDANCE_PHRASES.values())
    for aim in AIM_PHRASES.values():
        phrases.update(aim.values())
    return sorted(phrases)


# Högprioriterade klasser (akutlarm). Används av DetectionFilter och för cachen.
EMERGENCY_LABELS = ("person", "bil", "buss", "lastbil", "motorcykel", "cykel", "trafikljus", "stoppskylt")


def common_phrases(labels=EMERGENCY_LABELS):
    """Alla akutfraser 0,1–3,0 m för givna labels. Genereras i förväg vid start."""
    phrases = {"Trappa ner."}
    for label in labels:
        for d10 in range(1, 31):
            phrases.add(format_phrase(label, d10 / 10))
    return sorted(phrases)
