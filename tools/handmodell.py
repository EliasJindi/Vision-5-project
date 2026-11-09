# ===================== NY FIL AV CLAUDE (2026-11-09) =====================
# Mätverktyg, steg A för handmodellen (Elias 9/11: "vi testar med handmodellen för att se om det fungerar").
# I dag är "handen" det närmaste föremålet inom en armlängd i djupbilden (hand_region.py). Det tar
# ibland dörren, hushållspappret eller bordet (mosaikerna 7/11). Här körs en färdigtränad handmodell,
# MediaPipes handflatedetektor, på kamerans egen processor bredvid skannerns handläge, och för varje
# bild jämförs: hittade djupet ett närmaste föremål (blå ruta), hittade modellen en hand (grön ruta),
# och ligger handen i den blå rutan? Ändrar ingenting i skannern. Avgör om steg B (bygga in den) lönar sig.
#   python3 tools/handmodell.py                 (4K, 45 s)
#   clear && sleep 15 && python3 tools/handmodell.py --sekunder 60
# Gör så här under körningen: håll fram olika varor som vanligt, men sänk också handen ibland så att
# något annat är närmast (bordet, dörren). Då syns både om modellen hittar handen med varan, och om
# den låter bli när det inte är en hand. Ctrl+C avslutar och sammanfattar.
# Modellen: MediaPipe palm detection (Google, Apache 2.0), omvandlad för OAK-kameran av
# github.com/geaxgx/depthai_hand_tracker (palm_detection_sh4.blob, 128x128, 896 rutor). Den laddas ner
# till models/ första gången (4,7 MB, kontrolleras med sha256). models/ läggs aldrig upp på GitHub.
# Avkodningen nedan följer MediaPipes palm_detection-inställningar (SSD-ankare, 4 lager, steg 8/16/16/16).
# =========================================================================
import argparse
import hashlib
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # projektets rot

import numpy as np   # noqa: E402  (efter sökvägen ovan, som de andra verktygen)

MODEL_PATH = "models/palm_detection_sh4.blob"
MODEL_URL = "https://raw.githubusercontent.com/geaxgx/depthai_hand_tracker/main/models/palm_detection_sh4.blob"
MODEL_SHA256 = "4d45ecfddc68d8365fef3cb633d78b916612f25f7a48898f90f8a47d4b151aa5"
INPUT = 128           # modellens bild: 128 x 128
TILE_W, TILE_H = 480, 270


@dataclass(frozen=True)
class Palm:
    """En handflata som modellen hittat. Koordinater 0-1 i den bild de gäller (se square_to_frame)."""
    score: float
    x0: float
    y0: float
    x1: float
    y1: float


def palm_anchors(size: int = INPUT) -> np.ndarray:
    """
    Mitten (x, y) på modellens 896 ankarrutor, i samma ordning som modellens utdata. MediaPipe:
    4 lager med steg 8, 16, 16, 16 och 2 rutor per lager och cell (fast storlek 1x1). Lagren med
    samma steg slås ihop: 16x16 celler x 2 + 8x8 celler x 6 = 512 + 384 = 896.
    """
    anchors = []
    for stride, per_cell in ((8, 2), (16, 6)):
        cells = math.ceil(size / stride)
        for y in range(cells):
            for x in range(cells):
                anchors += [((x + 0.5) / cells, (y + 0.5) / cells)] * per_cell
    return np.array(anchors, dtype=np.float32)


def decode_palms(scores: Sequence[float], regressors: Sequence[float], anchors: np.ndarray,
                 threshold: float = 0.5, size: int = INPUT) -> List[Palm]:
    """
    Modellens utdata till rutor (0-1 i den kvadratiska bilden). scores: 896 råvärden (före sigmoid).
    regressors: 896 x 18 (mitt x, mitt y, bredd, höjd i pixlar relativt ankaret, sedan 7 punkter).
    """
    raw = np.clip(np.asarray(scores, dtype=np.float32).reshape(-1), -100, 100)   # som MediaPipe
    prob = 1 / (1 + np.exp(-raw))
    reg = np.asarray(regressors, dtype=np.float32).reshape(len(anchors), -1)
    palms = []
    for i in np.nonzero(prob > threshold)[0]:
        cx = reg[i, 0] / size + anchors[i, 0]
        cy = reg[i, 1] / size + anchors[i, 1]
        w, h = reg[i, 2] / size, reg[i, 3] / size
        if w <= 0 or h <= 0:
            continue
        palms.append(Palm(float(prob[i]), float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2)))
    return palms


def iou(a: Palm, b: Palm) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    union = (a.x1 - a.x0) * (a.y1 - a.y0) + (b.x1 - b.x0) * (b.y1 - b.y0) - inter
    return inter / union if union > 0 else 0.0


def non_max_suppression(palms: List[Palm], overlap: float = 0.3, keep: int = 2) -> List[Palm]:
    """Bästa rutan per hand: rutor som täcker en bättre till mer än overlap tas bort. Högst keep händer."""
    kept: List[Palm] = []
    for p in sorted(palms, key=lambda p: -p.score):
        if all(iou(p, k) <= overlap for k in kept):
            kept.append(p)
        if len(kept) == keep:
            break
    return kept


def square_to_frame(palm: Palm, width: int, height: int) -> Palm:
    """
    Från den kvadratiska modellbilden till kamerabilden (0-1). Kamerabilden (bredare än hög) läggs
    i mitten av kvadraten med svarta kanter över och under, se letterbox().
    """
    pad = (width - height) / 2 / width          # kanten ovanför, som andel av kvadratens sida
    scale = width / height                      # en enhet i kvadraten = så många bildhöjder
    def y(v: float) -> float:
        return min(1.0, max(0.0, (v - pad) * scale))
    return Palm(palm.score, min(1.0, max(0.0, palm.x0)), y(palm.y0), min(1.0, max(0.0, palm.x1)), y(palm.y1))


def letterbox_rows(width: int, height: int, size: int = INPUT) -> Tuple[int, int, int]:
    """(bildens höjd i modellbilden, svart kant över, svart kant under) för en bild width x height."""
    h = round(size * height / width)
    top = (size - h) // 2
    return h, top, size - h - top


def overlaps(region, palm: Palm, margin: float = 0.05, share: float = 0.25) -> bool:
    """
    Ligger handen i den blå rutan (hand_region.NearRegion)? Minst share av handens ruta ska ligga
    inom den blå rutan, utökad med margin (handen kan sticka ut lite bakom varan).
    """
    x0, y0 = region.x0 - margin, region.y0 - margin
    x1, y1 = region.x1 + margin, region.y1 + margin
    ix = max(0.0, min(x1, palm.x1) - max(x0, palm.x0))
    iy = max(0.0, min(y1, palm.y1) - max(y0, palm.y0))
    area = (palm.x1 - palm.x0) * (palm.y1 - palm.y0)
    return area > 0 and ix * iy / area >= share


def summarize(rows: Sequence[Tuple[bool, bool, bool]]) -> dict:
    """rows: [(närmast hittat, hand hittad, handen i närmast-rutan)] per bild."""
    return {
        "bilder": len(rows),
        "narmast": sum(1 for near, _, _ in rows if near),
        "hand": sum(1 for _, hand, _ in rows if hand),
        "bekraftad": sum(1 for near, _, ok in rows if near and ok),
        "narmast_utan_hand": sum(1 for near, _, ok in rows if near and not ok),   # annat föremål, eller missad hand
        "hand_utan_narmast": sum(1 for near, hand, _ in rows if hand and not near),
        "ingenting": sum(1 for near, hand, _ in rows if not near and not hand),
    }


def ensure_model(path: str = MODEL_PATH) -> str:
    """Laddar ner modellen första gången och kontrollerar att det är rätt fil."""
    if not os.path.exists(path):
        import urllib.request
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"Laddar ner handmodellen (4,7 MB) till {path} …")
        urllib.request.urlretrieve(MODEL_URL, path + ".tmp")
        os.replace(path + ".tmp", path)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != MODEL_SHA256:
        os.remove(path)
        sys.exit(f"❌ {path} är inte den väntade modellen (sha256 {digest[:12]}…). Borttagen, kör igen.")
    return path


def report(rows, tiles, ms, scores) -> None:
    """Sammanfattning och mosaik. Anropas innan kameran stängs (som tools/streckkod.py)."""
    import cv2
    from tools.streckkod import pick_tiles
    os.makedirs("logs", exist_ok=True)
    s = summarize(rows)
    picked = [tiles[i][0] for i in pick_tiles([odd for _, odd in tiles])]   # där de inte är överens först
    while picked and len(picked) % 4:
        picked.append(np.zeros((TILE_H, TILE_W, 3), np.uint8))
    if picked:
        cv2.imwrite("logs/handmodell.jpg", np.vstack([np.hstack(picked[i:i + 4]) for i in range(0, len(picked), 4)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"\nKlart: logs/handmodell.jpg (blå = närmast i djupet, grön = handmodellen). {s['bilder']} bilder.")
    print(f"  Närmaste föremål (dagens handruta): {s['narmast']}   Handmodellen hittade en hand: {s['hand']}")
    print(f"  Båda, och handen ligger i rutan (bekräftad):  {s['bekraftad']}")
    print(f"  Närmast men ingen hand i rutan:               {s['narmast_utan_hand']}"
          "   <- annat föremål, eller missade modellen handen? Se mosaiken")
    print(f"  Hand men inget närmaste föremål:              {s['hand_utan_narmast']}")
    print(f"  Ingenting:                                    {s['ingenting']}")
    if scores:
        print(f"  Modellens säkerhet när den hittade en hand: median {sorted(scores)[len(scores) // 2]:.2f}, "
              f"lägsta {min(scores):.2f}")
    if ms:
        print(f"  Handmodellen på kameran: median {sorted(ms)[len(ms) // 2]:.0f} ms per bild (max {max(ms):.0f} ms)")


def main():
    import cv2
    import depthai as dai

    import barcode_scanner as bs
    from hand_region import HandFocus, find_near_region

    ap = argparse.ArgumentParser(description="Hittar handmodellen handen med varan, och låter den bli annat?")
    ap.add_argument("--1080p", dest="hd", action="store_true", help="1080p i stället för 4K")
    ap.add_argument("--sekunder", type=float, default=45.0)
    ap.add_argument("--troskel", type=float, default=0.5, help="modellens säkerhet för att räknas som hand (0-1)")
    args = ap.parse_args()
    if not 0.05 <= args.troskel <= 0.95:
        sys.exit("--troskel ska ligga mellan 0,05 och 0,95")
    model = ensure_model()
    anchors = palm_anchors()

    pipeline = bs.build_pipeline(uhd=not args.hd, hand=True)   # samma kamera som skannern, oförändrad
    nn = pipeline.create(dai.node.NeuralNetwork)
    nn.setBlobPath(model)
    nn.input.setBlocking(True)
    nn.input.setQueueSize(1)
    palm_in = pipeline.create(dai.node.XLinkIn)
    palm_in.setStreamName("palm_in")
    palm_in.setMaxDataSize(INPUT * INPUT * 3)
    palm_in.out.link(nn.input)
    palm_out = pipeline.create(dai.node.XLinkOut)
    palm_out.setStreamName("palm_out")
    nn.out.link(palm_out.input)

    os.makedirs("logs", exist_ok=True)
    rows, ms, tiles, scores = [], [], [], []
    print("Startar kameran. Håll fram varor som vanligt, och sänk handen ibland så att något annat är närmast.")
    reported = False
    try:
        with dai.Device(pipeline) as device:
            q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
            q_in = device.getInputQueue("palm_in")
            q_out = device.getOutputQueue("palm_out", maxSize=1, blocking=True)
            control = device.getInputQueue("control")
            focus = HandFocus()
            t0 = last = time.time()
            try:
                while time.time() - t0 < args.sekunder:
                    msg = q.get()
                    now = time.time()
                    if now - last < 0.5:                          # samma takt som skannern i 4K
                        continue
                    last = now
                    color, depth = msg["color"].getCvFrame(), msg["depth"].getFrame()
                    region = find_near_region(depth)
                    command = focus.update(now, region)
                    if command is not None:
                        bs.send_focus(control, command, color.shape[1], color.shape[0])

                    # Handmodellen: hela bilden förminskad till 128 bred, svarta kanter till en kvadrat
                    h, top, bottom = letterbox_rows(color.shape[1], color.shape[0])
                    small = cv2.copyMakeBorder(cv2.resize(color, (INPUT, h), interpolation=cv2.INTER_AREA),
                                               top, bottom, 0, 0, cv2.BORDER_CONSTANT)
                    frame = dai.ImgFrame()
                    frame.setType(dai.ImgFrame.Type.BGR888p)
                    frame.setWidth(INPUT)
                    frame.setHeight(INPUT)
                    frame.setData(small.transpose(2, 0, 1).flatten())
                    t = time.perf_counter()
                    q_in.send(frame)
                    out = q_out.get()
                    ms.append((time.perf_counter() - t) * 1000)
                    palms = non_max_suppression(decode_palms(out.getLayerFp16("classificators"),
                                                             out.getLayerFp16("regressors"), anchors, args.troskel))
                    palms = [square_to_frame(p, color.shape[1], color.shape[0]) for p in palms]
                    scores += [p.score for p in palms]
                    ok = region is not None and any(overlaps(region, p) for p in palms)
                    rows.append((region is not None, bool(palms), ok))

                    if now - t0 >= 3 and len(tiles) < 200:           # efter uppstarten, högst 200 bilder
                        img = color.copy()
                        W, H = img.shape[1], img.shape[0]
                        if region is not None:
                            rx, ry, rw, rh = region.to_pixels(W, H)
                            cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 8)
                        for p in palms:
                            cv2.rectangle(img, (int(p.x0 * W), int(p.y0 * H)), (int(p.x1 * W), int(p.y1 * H)), (0, 220, 0), 10)
                        best = max((p.score for p in palms), default=0.0)
                        text = (f"narmast: {'JA' if region else 'nej'} | hand: {f'JA {best:.2f}' if palms else 'nej'}"
                                f" | i rutan: {'JA' if ok else 'nej'}")
                        tile = cv2.resize(img, (TILE_W, TILE_H))
                        cv2.putText(tile, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                        odd = (region is not None) != ok or (bool(palms) and region is None)   # inte överens
                        tiles.append((tile, odd))
                        print(f"  {now - t0:5.1f} s  {text}")
            except KeyboardInterrupt:
                print("\nAvbruten: sammanfattar det som hann samlas in.")
            report(rows, tiles, ms, scores)   # före stängningen, som kan ta några sekunder
            reported = True
            print("Stänger kameran …")
    except KeyboardInterrupt:
        if not reported:
            report(rows, tiles, ms, scores)


if __name__ == "__main__":
    main()
