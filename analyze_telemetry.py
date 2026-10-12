# ===================== ÄNDRINGAR AV CLAUDE (2026-10-10) =====================
# - Latens mäts till audio_start (ljudet börjar) när det finns; äldre loggar varnas.
# - Visar cacheträffar, syntestid, spänning, % underspänning, Gemini-fel och
#   varför meddelanden kastades (ttl/superseded).
# =============================================================================
"""
analyze_telemetry.py - Sammanfattar en loggsession.

Användning:
    python3 analyze_telemetry.py                      # senaste sessionen i logs/
    python3 analyze_telemetry.py logs/session_X.jsonl
"""
import glob
import json
import os
import sys
from collections import Counter


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def fmt(v, unit="ms"):
    return "-" if v is None else f"{v * 1000:.0f} {unit}"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else max(
        glob.glob("logs/session_*.jsonl"), key=os.path.getmtime
    )
    
    # --- NY FIX FÖR STRÖMAVBROTT ---
    ev = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            clean_line = line.strip().strip('\x00')
            if clean_line:
                try:
                    ev.append(json.loads(clean_line))
                except json.JSONDecodeError:
                    pass  # Ignorera trasig rad om strömmen bröts
    # -------------------------------

    if not ev:
        print("Tom logg.")
        return

    duration = ev[-1]["t"] - ev[0]["t"]
    minutes = max(duration / 60, 1e-9)
    print(f"Session: {path}")
    print(f"Längd: {duration:.0f} s\n")

    enq = {e["id"]: e for e in ev if e["event"] == "speak_enqueued"}
    start = {e["id"]: e for e in ev if e["event"] == "speak_start"}
    # audio_start = när ljudet faktiskt börjar spelas (finns från och med TTS-cachen).
    # Äldre loggar saknar det: då används speak_start, som bara mäter kön.
    audio = {e["id"]: e for e in ev if e["event"] == "audio_start"}
    honest = bool(audio)
    played = audio if honest else start
    end = {e["id"]: e for e in ev if e["event"] == "speak_end"}
    dropped = [e for e in ev if e["event"] == "speak_dropped"]
    interrupted = [e for e in ev if e["event"] == "speak_interrupted"]

    # --- Pratighet ---
    by_prio = Counter(e["priority"] for e in enq.values())
    print("== Pratighet ==")
    print(f"Meddelanden insatta i kön: {len(enq)} ({len(enq) / minutes:.1f} per minut)")
    for p in sorted(by_prio):
        print(f"  nivå {p}: {by_prio[p]} ({by_prio[p] / minutes:.1f}/min)")
    print(f"Faktiskt uppspelade: {len(played)}")
    print(f"Kastade: {len(dropped)} {dict(Counter(e.get('reason') for e in dropped))}  (ttl = för gammalt, superseded = nyare larm fanns)")
    print(f"Avbrutna av akut varning: {len(interrupted)}")

    spoken_time = sum(end[i]["t"] - played[i]["t"] for i in end if i in played)
    print(f"Tid med tal: {spoken_time:.0f} s = {100 * spoken_time / max(duration, 1e-9):.0f}% av sessionen")
    durs = [end[i]["t"] - played[i]["t"] for i in end if i in played]
    print(f"Taltid per meddelande: median {fmt(pct(durs, 50))}, p95 {fmt(pct(durs, 95))}")

    # --- Latens ---
    lat = [played[i]["t"] - enq[i]["t_detect"] for i in played if i in enq]
    wait = [start[i]["t"] - enq[i]["t"] for i in start if i in enq]
    if honest:
        print("\n== Latens (detektion -> ljudet börjar spelas) ==")
    else:
        print("\n== Latens (detektion -> Piper startar) ==")
        print("  OBS: gammal logg utan audio_start. Röstmodellens laddtid (~0,85 s) ingår INTE.")
    print(f"Totalt:    median {fmt(pct(lat, 50))}, p95 {fmt(pct(lat, 95))}, max {fmt(max(lat) if lat else None)}")
    print(f"Bara köad: median {fmt(pct(wait, 50))}, p95 {fmt(pct(wait, 95))}")
    for p in sorted(by_prio):
        lp = [played[i]["t"] - enq[i]["t_detect"] for i in played if i in enq and enq[i]["priority"] == p]
        if lp:
            print(f"  nivå {p}: median {fmt(pct(lp, 50))}, p95 {fmt(pct(lp, 95))} (n={len(lp)})")

    if honest:
        hits = sum(1 for e in audio.values() if e.get("cache_hit"))
        synth = [e["synth_s"] for e in audio.values() if not e.get("cache_hit") and "synth_s" in e]
        print(f"Cacheträffar: {hits} av {len(audio)} ({100 * hits / len(audio):.0f}%)")
        if synth:
            print(f"Syntes vid cachemiss: median {fmt(pct(synth, 50))}, max {fmt(max(synth))}")
        print("  OBS: pw-play behöver ytterligare ca 0,1–0,4 s innan ljudet hörs i headsetet.")

    # --- Filter ---
    summ = Counter()
    for e in ev:
        if e["event"] == "filter_summary":
            for k, v in e.get("counts", {}).items():
                summ[k] += v
    if summ:
        print("\n== Filterbeslut (topp 10) ==")
        for k, v in summ.most_common(10):
            print(f"  {k}: {v}")

    # --- Gemini ---
    g = [e for e in ev if e["event"] == "gemini_end"]
    if g:
        durs_g = [e["duration"] for e in g]
        ok = sum(1 for e in g if e.get("ok"))
        print("\n== Gemini ==")
        print(f"Anrop: {len(g)} ({len(g) / minutes:.1f}/min), lyckade: {ok}")
        errs = Counter(e.get("error") for e in g if not e.get("ok") and e.get("error"))
        if errs:
            print(f"Fel: {dict(errs)}")
        print(f"Svarstid: median {fmt(pct(durs_g, 50))}, p95 {fmt(pct(durs_g, 95))}, max {fmt(max(durs_g))}")

    # --- Hårdvara ---
    v = [e for e in ev if e["event"] == "vitals"]
    if v:
        temps = [e["temp_c"] for e in v if e.get("temp_c") is not None]
        thr = Counter(e.get("throttled") for e in v)
        print("\n== Hårdvara ==")
        if temps:
            print(f"Temperatur: max {max(temps):.1f} C, snitt {sum(temps) / len(temps):.1f} C")
        print(f"Throttling-koder: {dict(thr)}  (0x0 = ren)")
        volts = [e["voltage_v"] for e in v if e.get("voltage_v") is not None]
        if volts:
            print(f"Spänning EXT5V: min {min(volts):.3f} V, median {pct(volts, 50):.3f} V  (Pi:n varnar under ca 4,63 V)")
        uv = [e["undervolt_now"] for e in v if e.get("undervolt_now") is not None]
        if uv:
            print(f"Underspänning just nu: {sum(uv)} av {len(uv)} prov ({100 * sum(uv) / len(uv):.0f}%)")
        qs = [e["audio_qsize"] for e in v if e.get("audio_qsize") is not None]
        if qs:
            print(f"Ljudköns längd: max {max(qs)}, snitt {sum(qs) / len(qs):.1f}")


if __name__ == "__main__":
    main()
