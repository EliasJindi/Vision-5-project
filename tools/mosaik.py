# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Lägger upp till 16 av --diag-bilderna i en bild, logs/mosaik_<NAMN>.jpg, med löpnummer och
# klockslag på varje. Så ser man vad kameran såg.
# Från 7/11 sparar skannern bilderna i en mapp per körning (logs/snapshots/scan_<datum>_<tid>_<läge>/),
# så äldre körningar finns kvar. Äldre bilder direkt i logs/snapshots/ fungerar också: där tas den
# senaste körningen (ett glapp över 20 s mellan bilderna betyder en äldre körning).
#   python3 tools/mosaik.py NAMN                      senaste körningen
#   python3 tools/mosaik.py NAMN mitten               mittersta halvan av körningen
#   python3 tools/mosaik.py NAMN 12:11:50 12:12:30    bara bilder mellan de tiderna
#   python3 tools/mosaik.py NAMN --senaste 4          en mosaik per körning för de 4 senaste
#   python3 tools/mosaik.py NAMN --korning scan_20261107_112104_4k
# Bilderna ligger i logs/, som aldrig läggs upp på GitHub (repot är publikt).
# =========================================================================
import argparse
import glob
import os
import sys

RUN_GAP_S = 20
MAX_TILES = 16
SNAP_DIR = os.path.join("logs", "snapshots")


def latest_run(files, mtime=os.path.getmtime):
    """Bilderna från den senaste körningen, i tidsordning."""
    if not files:
        return []
    files = sorted(files, key=mtime, reverse=True)
    run = [files[0]]
    for f in files[1:]:
        if mtime(run[-1]) - mtime(f) > RUN_GAP_S:
            break
        run.append(f)
    return run[::-1]


def hhmmss(path):
    """'snap_011_121233.jpg' -> '121233'."""
    return os.path.basename(path)[9:15]


def narrow(run, extra):
    """Ingen begränsning, 'mitten' eller två klockslag (HH:MM:SS). ValueError vid felaktig användning."""
    if not extra:
        return run
    if extra == ["mitten"]:
        a, b = len(run) // 4, len(run) - len(run) // 4
        return run[a:b] or run
    if len(extra) == 2:
        lo, hi = (x.replace(":", "") for x in extra)
        return [f for f in run if lo <= hhmmss(f) <= hi]
    raise ValueError("Använd: NAMN, NAMN mitten, eller NAMN HH:MM:SS HH:MM:SS")


def pick_even(run, n=MAX_TILES):
    """Högst n bilder, jämnt spridda över run."""
    n = min(n, len(run))
    return [run[round(i * (len(run) - 1) / max(1, n - 1))] for i in range(n)]


def list_runs(base=SNAP_DIR):
    """[(körningens namn, [bilder i tidsordning])], äldst först. Mappar per körning, annars de gamla bilderna."""
    runs = []
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):   # scan_<datum>_<tid>_<läge>: namnet sorterar i tidsordning
            files = sorted(glob.glob(os.path.join(base, name, "snap_*.jpg")))
            if files:
                runs.append((name, files))
    flat = latest_run(glob.glob(os.path.join(base, "snap_*.jpg")))
    if flat:
        runs.insert(0, ("gamla mappen", flat))
    return runs


def choose(runs, senaste=1, korning=None):
    """De körningar som ska visas, nyaste först. ValueError om korning inte finns."""
    if korning:
        match = [r for r in runs if r[0] == korning]
        if not match:
            raise ValueError(f"Ingen körning {korning!r}. Finns: {', '.join(n for n, _ in runs[-6:]) or 'inga'}")
        return match
    return runs[::-1][:max(1, senaste)]


def make_mosaic(files, out):
    import cv2
    import numpy as np
    w, h = 480, 270
    tiles = []
    for f in pick_even(files):
        t = hhmmss(f)
        img = cv2.imread(f)
        img = cv2.resize(img, (w, h)) if img is not None else np.zeros((h, w, 3), np.uint8)
        cv2.putText(img, f"{os.path.basename(f)[5:8]}  {t[0:2]}:{t[2:4]}:{t[4:6]}", (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        tiles.append(img)
    while len(tiles) % 4:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]),
                [cv2.IMWRITE_JPEG_QUALITY, 85])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mosaik av --diag-bilderna från en eller flera körningar")
    ap.add_argument("namn")
    ap.add_argument("urval", nargs="*", help="'mitten', eller två klockslag HH:MM:SS HH:MM:SS")
    ap.add_argument("--senaste", type=int, default=1, help="en mosaik per körning för de N senaste")
    ap.add_argument("--korning", help="en bestämd körning, t.ex. scan_20261107_112104_4k")
    args = ap.parse_args(argv)
    runs = list_runs()
    if not runs:
        sys.exit("Inga bilder i logs/snapshots/ (kör skannern med --diag)")
    try:
        chosen = choose(runs, args.senaste, args.korning)
    except ValueError as e:
        sys.exit(str(e))
    for i, (run_name, files) in enumerate(chosen):
        try:
            files = narrow(files, args.urval)
        except ValueError as e:
            sys.exit(str(e))
        if not files:
            print(f"{run_name}: inga bilder mellan {args.urval[0]} och {args.urval[1]}")
            continue
        out = os.path.join("logs", f"mosaik_{args.namn}.jpg" if len(chosen) == 1 else f"mosaik_{args.namn}_{i + 1}.jpg")
        make_mosaic(files, out)
        first, last = hhmmss(files[0]), hhmmss(files[-1])
        print(f"Klart: {out}  ({run_name}: {len(files)} bilder, {first[:2]}:{first[2:4]}:{first[4:]} till "
              f"{last[:2]}:{last[2:4]}:{last[4:]})")


if __name__ == "__main__":
    main()
