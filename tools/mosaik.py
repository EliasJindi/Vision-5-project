# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Lägger upp till 16 av --diag-bilderna (logs/snapshots/) från den SENASTE körningen i en bild,
# logs/mosaik_<NAMN>.jpg, med löpnummer och klockslag på varje. Så ser man vad kameran såg.
# Bilderna sparas var 2:a sekund; ett glapp över 20 s betyder en äldre körning, som inte tas med.
#   python3 tools/mosaik.py NAMN                      hela senaste körningen
#   python3 tools/mosaik.py NAMN mitten               mittersta halvan av körningen
#   python3 tools/mosaik.py NAMN 12:11:50 12:12:30    bara bilder mellan de tiderna
# Bilderna ligger i logs/, som aldrig läggs upp på GitHub (repot är publikt).
# =========================================================================
import glob
import os
import sys

RUN_GAP_S = 20
MAX_TILES = 16


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


def main(argv=None):
    import cv2
    import numpy as np
    args = sys.argv[1:] if argv is None else argv
    label, extra = (args[0] if args else "X"), args[1:]
    run = latest_run(glob.glob("logs/snapshots/snap_*.jpg"))
    if not run:
        sys.exit("Inga bilder i logs/snapshots/ (kör skannern med --diag)")
    try:
        run = narrow(run, extra)
    except ValueError as e:
        sys.exit(str(e))
    if not run:
        sys.exit(f"Inga bilder mellan {extra[0]} och {extra[1]} i senaste körningen")
    picked = pick_even(run)
    w, h = 480, 270
    tiles = []
    for f in picked:
        t = hhmmss(f)
        img = cv2.imread(f)
        img = cv2.resize(img, (w, h)) if img is not None else np.zeros((h, w, 3), np.uint8)
        cv2.putText(img, f"{os.path.basename(f)[5:8]}  {t[0:2]}:{t[2:4]}:{t[4:6]}", (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        tiles.append(img)
    while len(tiles) % 4:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    out = f"logs/mosaik_{label}.jpg"
    cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]),
                [cv2.IMWRITE_JPEG_QUALITY, 85])
    first, last = hhmmss(run[0]), hhmmss(run[-1])
    print(f"Klart: {out}. {len(run)} bilder, {first[:2]}:{first[2:4]}:{first[4:]} till "
          f"{last[:2]}:{last[2:4]}:{last[4:]}, {len(picked)} med")


if __name__ == "__main__":
    main()
