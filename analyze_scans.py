# ===================== NY FIL AV CLAUDE (2026-10-20) =====================
# Utvärderar filtren i barcode_scanner.py (ändring 20-22) på skannerloggarna:
# - Höjdregler: hur många felläsningar varje regel stoppar och hur många rätta den kastar.
#   Körs även utan körningen med flest fel, så att en enda körning inte avgör.
# - Orimligt djup: vilka läsningar som har det, varifrån djupet togs (depth_how) och hur
#   långt in i körningen de kom. Gamla loggar utan de nya fälten räknas om från hornen.
# Läser bara loggarna, ändrar ingenting. Trasiga rader (strömavbrott) hoppas över.
# Reglerna läses från scan_filters.py, så skriptet går även på en dator utan kameran.
# =========================================================================
"""
analyze_scans.py - Utvärderar höjd- och djupfiltren på skannerloggarna.

Användning:
    python3 analyze_scans.py                              # alla logs/scan_*.jsonl
    python3 analyze_scans.py logs/scan_20261020_*.jsonl   # bara vissa loggar
    python3 analyze_scans.py --utan 20261017_140916       # utan körningar vars namn innehåller texten
"""
import argparse
import glob
import json
import os
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


def main():
    ap = argparse.ArgumentParser(description="Utvärderar höjd- och djupfiltren på skannerloggarna")
    ap.add_argument("loggar", nargs="*")
    ap.add_argument("--utan", action="append", default=[], metavar="TEXT",
                    help="hoppa över loggar vars namn innehåller TEXT (kan anges flera gånger)")
    args = ap.parse_args()
    paths = sorted(args.loggar or glob.glob("logs/scan_*.jsonl"))
    paths = [p for p in paths if not any(u in os.path.basename(p) for u in args.utan)]
    if not paths:
        raise SystemExit("Inga loggar hittades.")
    logs = {os.path.basename(p): read_log(p) for p in paths}

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
