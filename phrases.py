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


# Högprioriterade klasser (akutlarm). Används av DetectionFilter och för cachen.
EMERGENCY_LABELS = ("person", "bil", "buss", "lastbil", "motorcykel", "cykel", "trafikljus", "stoppskylt")


def common_phrases(labels=EMERGENCY_LABELS):
    """Alla akutfraser 0,1–3,0 m för givna labels. Genereras i förväg vid start."""
    phrases = {"Trappa ner."}
    for label in labels:
        for d10 in range(1, 31):
            phrases.add(format_phrase(label, d10 / 10))
    return sorted(phrases)
