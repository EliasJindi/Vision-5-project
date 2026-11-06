# ===================== NY FIL AV CLAUDE (2026-10-20) =====================
# Utvärderar filtren i barcode_scanner.py (ändring 20-22) på skannerloggarna:
# - Höjdregler: hur många felläsningar varje regel stoppar och hur många rätta den kastar.
#   Körs även utan körningen med flest fel, så att en enda körning inte avgör.
# - Orimligt djup: vilka läsningar som har det, varifrån djupet togs (depth_how) och hur
#   långt in i körningen de kom. Gamla loggar utan de nya fälten räknas om från hornen.
# Läser bara loggarna, ändrar ingenting. Trasiga rader (strömavbrott) hoppas över.
# Reglerna läses från scan_filters.py, så skriptet går även på en dator utan kameran.
# 2026-11-06: --pixlar visar, per läge, hur ofta läsningarna är säkra respektive osäkra (tunna eller
#   ogiltig kontrollsiffra) vid olika px/modul. Underlag för om röstvägledningen ska säga "håll stilla"
#   i stället för "lite närmare" när en osäker kod redan är stor nog. Samma definition av säker som
#   rösten (voice_guidance.model.CodeRead). Utan flaggan är utskriften som förut.
# =========================================================================
"""
analyze_scans.py - Utvärderar höjd- och djupfiltren på skannerloggarna.

Användning:
    python3 analyze_scans.py                              # alla logs/scan_*.jsonl
    python3 analyze_scans.py logs/scan_20261020_*.jsonl   # bara vissa loggar
    python3 analyze_scans.py --utan 20261017_140916       # utan körningar vars namn innehåller texten
    python3 analyze_scans.py --pixlar                     # säkra/osäkra läsningar per px/modul (röstvägledningen)
"""
import argparse
import glob
import json
import os
import statistics
from collections import Counter

from scan_filters import DEPTH_FACTOR, MIN_HEIGHT_RATIO, depth_plausible, expected_depth, size_from_corners

RATIO_LIMITS = (0.05, 0.10, 0.15, 0.20)
PX_LIMITS = (5, 10, 15, 20, 30)
BOTH_PX = 20                # "båda": tunn som andel OCH färre pixlar än så (skyddar korta men hela koder)


def read_log(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip().strip("\x00")
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def height(rec):
    """(höjd i px, höjd/bredd), från loggens fält eller räknat ur hornen i äldre loggar."""
    if "h_px" in rec and rec.get("w_px"):
        return rec["h_px"], rec["h_px"] / rec["w_px"]
    corners, w = rec.get("hornen"), rec.get("w_px")
    if not corners or not w:
        return None
    _, h = size_from_corners(*corners)
    return h, h / w


def height_rules(reads, title):
    right = [hr for hr, ok in reads if ok]
    wrong = [hr for hr, ok in reads if not ok]
    print(f"\n{title}: {len(right)} rätta, {len(wrong)} fel")
    if not wrong:
        return
    rules = [(f"andel < {g:.0%}", lambda h, r, g=g: r < g) for g in RATIO_LIMITS]
    rules += [(f"höjd < {p} px", lambda h, r, p=p: h < p) for p in PX_LIMITS]
    rules.append((f"andel < {MIN_HEIGHT_RATIO:.0%} och höjd < {BOTH_PX} px",
                  lambda h, r: r < MIN_HEIGHT_RATIO and h < BOTH_PX))
    for name, rule in rules:
        stopped = sum(rule(h, r) for h, r in wrong)
        lost = sum(rule(h, r) for h, r in right)
        print(f"  {name:28s} stoppar {stopped:3d} av {len(wrong)} fel ({stopped / len(wrong):4.0%}), "
              f"kastar {lost:4d} av {len(right)} rätta ({lost / max(len(right), 1):4.0%})")


PX_EDGES = (1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5)   # gränser för px/modul-grupperna
HOLD_LIMITS = (2.25, 2.5, 2.75, 3.0)                     # tänkta trösklar för "håll stilla"


def mode_of(rec, log_name):
    """Läget ur raden, annars ur filnamnet (scan_<datum>_<tid>_<läge>.jsonl)."""
    if rec.get("mode"):
        return rec["mode"]
    for mode in ("4k", "1080p"):
        if log_name.endswith(f"_{mode}.jsonl"):
            return mode
    return "okänt"


def pixel_samples(logs):
    """{läge: [(px_per_modul, säker, loggnamn), ...]}. Rader utan px eller hörn hoppas över."""
    from voice_guidance.model import CodeRead   # samma regel som rösten; importeras här så att resten går utan
    samples = {}
    for name, rows in logs.items():
        for rec in rows:
            px = rec.get("px_per_modul")
            if not isinstance(px, (int, float)) or px <= 0:
                continue
            try:
                reliable = CodeRead.from_record(rec).reliable
            except ValueError:
                continue
            samples.setdefault(mode_of(rec, name), []).append((float(px), reliable, name))
    return samples


def bucket_of(px):
    for i, edge in enumerate(PX_EDGES):
        if px < edge:
            return i
    return len(PX_EDGES)


def bucket_label(i):
    if i == 0:
        return f"under {PX_EDGES[0]:.2f}"
    if i == len(PX_EDGES):
        return f"minst {PX_EDGES[-1]:.2f}"
    return f"{PX_EDGES[i - 1]:.2f}–{PX_EDGES[i]:.2f}"


def quantile(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def comma(x, digits=2):
    return f"{x:.{digits}f}".replace(".", ",")


def pixel_report(logs):
    samples = pixel_samples(logs)
    if not samples:
        print("Inga läsningar med px/modul och hörn i loggarna.")
        return
    print("Säkra och osäkra läsningar per px/modul. Osäker = tunn remsa eller ogiltig kontrollsiffra:")
    print("då säger rösten \"lite närmare\" eller en riktning. Varje körning räknas med alla sina läsningar,")
    print("så titta på kolumnen körningar: en grupp från en enda körning säger lite.")
    for mode in sorted(samples):
        rows = samples[mode]
        safe = [px for px, ok, _ in rows if ok]
        unsafe = [px for px, ok, _ in rows if not ok]
        print(f"\n{mode}: {len(safe)} säkra, {len(unsafe)} osäkra, från {len({n for *_, n in rows})} körningar")
        print(f"  {'px/modul':12s} {'säkra':>6s} {'osäkra':>7s} {'andel säkra':>12s} {'körningar':>10s}")
        for i in range(len(PX_EDGES) + 1):
            group = [(ok, n) for px, ok, n in rows if bucket_of(px) == i]
            if not group:
                continue
            n_safe = sum(ok for ok, _ in group)
            print(f"  {bucket_label(i).replace('.', ','):12s} {n_safe:6d} {len(group) - n_safe:7d} "
                  f"{n_safe / len(group):11.0%} {len({n for _, n in group}):10d}")
        for label, values in (("Osäkra", unsafe), ("Säkra", safe)):
            if values:
                print(f"  {label}: median {comma(statistics.median(values))} px/modul "
                      f"(10–90 %: {comma(quantile(values, 0.1))}–{comma(quantile(values, 0.9))})")
        if unsafe:
            print("  Tänkt regel: osäker men minst T px/modul -> \"håll stilla\" i stället för \"lite närmare\"")
            for limit in HOLD_LIMITS:
                hold = sum(px >= limit for px in unsafe)
                big = [ok for px, ok, _ in rows if px >= limit]
                share = f"{sum(big) / len(big):.0%} av läsningarna var säkra" if big else "inga läsningar"
                print(f"    T = {comma(limit)}: {hold} av {len(unsafe)} osäkra skulle få \"håll stilla\"; "
                      f"vid minst T: {share} ({len(big)} st)")


def main():
    ap = argparse.ArgumentParser(description="Utvärderar höjd- och djupfiltren på skannerloggarna")
    ap.add_argument("loggar", nargs="*")
    ap.add_argument("--utan", action="append", default=[], metavar="TEXT",
                    help="hoppa över loggar vars namn innehåller TEXT (kan anges flera gånger)")
    ap.add_argument("--pixlar", action="store_true",
                    help="visa bara säkra/osäkra läsningar per px/modul (underlag för röstvägledningen)")
    args = ap.parse_args()
    paths = sorted(args.loggar or glob.glob("logs/scan_*.jsonl"))
    paths = [p for p in paths if not any(u in os.path.basename(p) for u in args.utan)]
    if not paths:
        raise SystemExit("Inga loggar hittades.")
    logs = {os.path.basename(p): read_log(p) for p in paths}
    if args.pixlar:
        pixel_report(logs)
        return

    # --- Höjd ---
    per_file = {}
    for name, rows in logs.items():
        per_file[name] = [(hr, r["correct"]) for r in rows
                          if "correct" in r and r.get("ean") and (hr := height(r))]
    all_reads = [x for reads in per_file.values() for x in reads]
    print(f"Loggar: {len(logs)}. Läsningar med facit och hörn: {len(all_reads)}")
    height_rules(all_reads, "Höjdregler, alla loggar")
    worst = max(per_file, key=lambda n: sum(not ok for _, ok in per_file[n]))
    if len(per_file) > 1 and sum(not ok for _, ok in per_file[worst]):
        rest = [x for n, reads in per_file.items() if n != worst for x in reads]
        height_rules(rest, f"Höjdregler utan {worst} (flest fel)")

    # --- Djup ---
    print(f"\nOrimligt djup (mer än {DEPTH_FACTOR} gånger från det kodens storlek säger):")
    sources, n_depth = Counter(), 0
    for name, rows in logs.items():
        first_t = rows[0]["t"] if rows and "t" in rows[0] else None
        bad = []
        for r in rows:
            d = r.get("distance_m")
            expected = expected_depth(r.get("px_per_modul"), r.get("mode"))
            if d is None or expected is None:
                continue
            n_depth += 1
            if not depth_plausible(d, expected):
                bad.append((r, expected))
                sources[r.get("depth_how", "?")] += 1
        if bad:
            print(f"  {name}: {len(bad)} st")
            for r, expected in bad:
                after = f"{r['t'] - first_t:5.1f} s" if first_t is not None else "?"
                print(f"    {r['distance_m']:6.2f} m (väntat ~{expected:.2f}), "
                      f"källa: {r.get('depth_how', '?')}, {after} efter första läsningen")
    print(f"  Totalt {sum(sources.values())} av {n_depth} läsningar med djup. Källa: "
          + (", ".join(f"{k} {v}" for k, v in sources.items()) or "–"))


if __name__ == "__main__":
    main()
