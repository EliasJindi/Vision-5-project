# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Steg 1 av "fokus på handen med varan" (Elias 6/11): visar om kameran hittar det som hålls fram.
# Tar några bilder med en sekunds mellanrum, ritar en ruta runt det närmaste föremålet inom en
# armlängd (hand_region.find_near_region) och sparar dem som en mosaik i logs/narmast.jpg.
# Ändrar ingenting i skannern. Kör utan att skannern är igång:
#   python3 tools/narmast.py            (1080p, 8 bilder)
#   python3 tools/narmast.py --4k       (samma upplösning som varutesterna)
# Flytta varan mellan bilderna: högt, lågt, åt sidorna, nära och längre bort.
# =========================================================================
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # projektets rot

import cv2                                    # noqa: E402
import depthai as dai                         # noqa: E402
import numpy as np                            # noqa: E402

import barcode_scanner as bs                  # noqa: E402  samma kamerainställning som skannern
from hand_region import find_near_region      # noqa: E402

TILE_W, TILE_H = 480, 270


def latest(q, wait_s):
    """Den senaste bilden efter wait_s sekunder (äldre slängs, så att bilden är aktuell)."""
    msg, t0 = None, time.time()
    while time.time() - t0 < wait_s or msg is None:
        msg = q.get()
    return msg


def tile(color, region, n):
    img = cv2.resize(color, (TILE_W, TILE_H))
    if region is None:
        text, colour = f"{n}: ingen hand", (0, 0, 255)
    else:
        x, y, w, h = region.to_pixels(TILE_W, TILE_H)
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 3)
        text, colour = f"{n}: {region.depth_m:.2f} m", (0, 255, 0)
    cv2.putText(img, text, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)
    return img


def main():
    ap = argparse.ArgumentParser(description="Hittar kameran handen med varan? (närmaste föremålet i djupet)")
    ap.add_argument("--4k", dest="uhd", action="store_true", help="3840x2160 som i varutesterna")
    ap.add_argument("--antal", type=int, default=8, help="antal bilder (standard 8)")
    args = ap.parse_args()
    os.makedirs("logs", exist_ok=True)
    print("Startar kameran. Håll varan framför dig och flytta den mellan bilderna (en per sekund).")
    tiles, found = [], 0
    with dai.Device(bs.build_pipeline(uhd=args.uhd)) as device:
        q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
        latest(q, 3.0)                                       # låt autofokus, ljus och djup ställa in sig
        for n in range(1, args.antal + 1):
            msg = latest(q, 1.0)
            color, depth = msg["color"].getCvFrame(), msg["depth"].getFrame()
            region = find_near_region(depth)
            found += region is not None
            where = "ingen hand hittad" if region is None else (
                f"x {region.x0:.0%}–{region.x1:.0%}, y {region.y0:.0%}–{region.y1:.0%}, {region.depth_m:.2f} m")
            print(f"  {n}: {where}")
            tiles.append(tile(color, region, n))
    while len(tiles) % 4:
        tiles.append(np.zeros((TILE_H, TILE_W, 3), np.uint8))
    cv2.imwrite("logs/narmast.jpg", np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]),
                [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"Klart: logs/narmast.jpg. Hand hittad i {found} av {args.antal} bilder. "
          "Grön ruta = det kameran tror är handen med varan.")


if __name__ == "__main__":
    main()
