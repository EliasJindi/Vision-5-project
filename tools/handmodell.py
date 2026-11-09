# ===================== NY FIL AV CLAUDE (2026-11-09) =====================
# Mätverktyg, steg A för handmodellen (Elias 9/11: "vi testar med handmodellen för att se om det fungerar").
# I dag är "handen" det närmaste föremålet inom en armlängd i djupbilden (hand_region.py). Det tar
# ibland dörren, hushållspappret eller bordet (mosaikerna 7/11). Här körs en färdigtränad handmodell,
# MediaPipes handflatedetektor, på kamerans egen processor bredvid skannerns handläge, och för varje
# bild jämförs: hittade djupet ett närmaste föremål (blå ruta), hittade modellen en hand (grön ruta),
# och ligger handen i den blå rutan? Ändrar ingenting i skannern. Avgör om steg B (bygga in den) lönar sig.
#   python3 tools/handmodell.py                 (4K, 60 s)
#   clear && sleep 15 && python3 tools/handmodell.py --sekunder 60
#   clear && sleep 5 && python3 tools/handmodell.py --sekunder 40 --namn dorr   (egen mosaik per körning)
# Gör så här under körningen: håll fram olika varor som vanligt, men sänk också handen ibland så att
# något annat är närmast (bordet, dörren). Då syns både om modellen hittar handen med varan, och om
# den låter bli när det inte är en hand. Ctrl+C avslutar och sammanfattar.
# Modellen: MediaPipe palm detection (Google, Apache 2.0), omvandlad för OAK-kameran av
# github.com/geaxgx/depthai_hand_tracker (palm_detection_sh4.blob, 128x128, 896 rutor). Den laddas ner
# till models/ första gången (4,7 MB, kontrolleras med sha256). models/ läggs aldrig upp på GitHub.
# Avkodningen nedan följer MediaPipes palm_detection-inställningar (SSD-ankare, 4 lager, steg 8/16/16/16).
# 2026-11-09 (andra körningen): på hela bilden hittade modellen handen dåligt (säkerhet median 0,54, "nej"
#   på bilder med tydliga händer) och gav falsklarm på dörrkarmen. Hela 4K-bilden blir 128x128 och
#   handen 15-20 pixlar; modellens upphovsman skriver att de svarta kanterna gör det värre och att det
#   hjälper att skära ut området runt handen. Därför körs modellen nu två gånger per bild: på hela bilden
#   (som förut) och på den blå rutan, utskuren som en kvadrat och förstorad (square_crop). Sammanfattningen
#   jämför dem. Djupet säger VAR handen troligen är, modellen avgör OM det är en hand.
# 2026-11-09 (Elias: "är du säker på att det är pga konsekventa saker?"): --namn ger en mosaik per körning,
#   och sammanfattningen visar regeln för steg B direkt: blå ruta bekräftad om en hand setts i den inom 2 s.
# =========================================================================
import argparse
import hashlib
import math
import os
import re
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


def square_crop(region, width: int, height: int, margin: float = 0.15, min_share: float = 0.2) -> Tuple[int, int, int]:
    """
    En kvadrat (x, y, sida i pixlar) runt den blå rutan (hand_region.NearRegion), med margin av sidan
    runt om, flyttad så att den ligger helt i bilden. Sidan är minst min_share av bildhöjden (en liten
    ruta förstoras annars väldigt mycket) och högst bildhöjden.
    """
    rw, rh = (region.x1 - region.x0) * width, (region.y1 - region.y0) * height
    side = int(round(max(rw, rh) * (1 + 2 * margin)))
    side = max(int(min_share * height), min(height, side), 1)
    cx, cy = (region.x0 + region.x1) / 2 * width, (region.y0 + region.y1) / 2 * height
    x = int(round(min(max(cx - side / 2, 0), width - side)))
    y = int(round(min(max(cy - side / 2, 0), height - side)))
    return x, y, side


def crop_to_frame(palm: Palm, box: Tuple[int, int, int], width: int, height: int) -> Palm:
    """Från den utskurna kvadraten (0-1) till kamerabilden (0-1)."""
    x, y, side = box
    def fx(v: float) -> float:
        return min(1.0, max(0.0, (x + v * side) / width))
    def fy(v: float) -> float:
        return min(1.0, max(0.0, (y + v * side) / height))
    return Palm(palm.score, fx(palm.x0), fy(palm.y0), fx(palm.x1), fy(palm.y1))


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


def median_text(values: Sequence[float], fmt: str = "{:.2f}") -> str:
    """'median (lägsta–högsta)', eller '-' om inget finns."""
    if not values:
        return "-"
    v = sorted(values)
    return f"{fmt.format(v[len(v) // 2])} ({fmt.format(v[0])}-{fmt.format(v[-1])})"


def confirmed_within(rows: Sequence[Tuple[float, bool, bool]], window: float = 2.0) -> Tuple[int, int]:
    """
    Regeln som föreslås för skannern (steg B): den blå rutan räknas som en hand om modellen har hittat
    en hand i den någon gång de senaste window sekunderna (den här bilden medräknad).
    rows: [(tid, blå ruta finns, hand i den blå rutan)] i tidsordning. Returnerar (bekräftade, blå rutor).
    """
    last_ok, confirmed, total = float("-inf"), 0, 0
    for t, near, ok in rows:
        if near and ok:
            last_ok = t
        if near:
            total += 1
            if t - last_ok <= window:
                confirmed += 1
    return confirmed, total


def share_text(part: int, total: int) -> str:
    """'7 av 10 (70 %)', eller '-' om total är 0."""
    return f"{part} av {total} ({round(100 * part / total)} %)" if total else "-"


def mosaic_path(name: str = "") -> str:
    """logs/handmodell.jpg, eller logs/handmodell_<namn>.jpg så att körningarna inte skriver över varandra."""
    return f"logs/handmodell_{name}.jpg" if name else "logs/handmodell.jpg"


def report(rows, tiles, ms, scores, path: str = "logs/handmodell.jpg") -> None:
    """
    Sammanfattning och mosaik. Anropas innan kameran stängs (som tools/streckkod.py).
    rows: [(tid, närmast, hand hela, i rutan hela, hand ruta, i rutan ruta)]. ms och scores: {"hela": [], "ruta": []}.
    """
    import cv2
    from tools.streckkod import pick_tiles
    os.makedirs("logs", exist_ok=True)
    whole = summarize([(r[1], r[2], r[3]) for r in rows])
    crop = summarize([(r[1], r[4], r[5]) for r in rows])
    rule_whole = share_text(*confirmed_within([(r[0], r[1], r[3]) for r in rows]))
    rule_crop = share_text(*confirmed_within([(r[0], r[1], r[5]) for r in rows]))
    picked = [tiles[i][0] for i in pick_tiles([odd for _, odd in tiles])]   # där rutan missade först
    while picked and len(picked) % 4:
        picked.append(np.zeros((TILE_H, TILE_W, 3), np.uint8))
    if picked:
        cv2.imwrite(path, np.vstack([np.hstack(picked[i:i + 4]) for i in range(0, len(picked), 4)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"\nKlart: {path}. {whole['bilder']} bilder, närmaste föremål (blå) i {whole['narmast']}.")
    print("  Blå = närmast i djupet. Gul = modellen på hela bilden. Grön = modellen på den utskurna rutan.")
    print(f"  {'':42}{'Hela bilden':>18}{'Utskuren ruta':>20}")
    print(f"  {'Hittade en hand':42}{whole['hand']:>18}{crop['hand']:>20}")
    print(f"  {'Handen i den blå rutan (bekräftad)':42}{whole['bekraftad']:>18}{crop['bekraftad']:>20}")
    print(f"  {'Bekräftad inom 2 s (regeln för steg B)':42}{rule_whole:>18}{rule_crop:>20}"
          "   <- med vara: högt är bra. Utan händer: 0 är bra")
    print(f"  {'Blå ruta men ingen hand':42}{whole['narmast_utan_hand']:>18}{crop['narmast_utan_hand']:>20}"
          "   <- annat föremål, eller missad hand? Se mosaiken")
    print(f"  {'Hand utan blå ruta (falsklarm?)':42}{whole['hand_utan_narmast']:>18}{'-':>20}")
    print(f"  {'Säkerhet, median (lägsta-högsta)':42}{median_text(scores['hela']):>18}{median_text(scores['ruta']):>20}")
    print(f"  {'Tid på kameran, ms':42}{median_text(ms['hela'], '{:.0f}'):>18}{median_text(ms['ruta'], '{:.0f}'):>20}")


def main():
    import cv2
    import depthai as dai

    import barcode_scanner as bs
    from hand_region import HandFocus, find_near_region

    ap = argparse.ArgumentParser(description="Hittar handmodellen handen med varan, och låter den bli annat?")
    ap.add_argument("--1080p", dest="hd", action="store_true", help="1080p i stället för 4K")
    ap.add_argument("--sekunder", type=float, default=60.0)
    ap.add_argument("--troskel", type=float, default=0.5, help="modellens säkerhet för att räknas som hand (0-1)")
    ap.add_argument("--namn", default="", help="mosaiken sparas som logs/handmodell_NAMN.jpg (t.ex. vara1, dorr)")
    args = ap.parse_args()
    if not 0.05 <= args.troskel <= 0.95:
        sys.exit("--troskel ska ligga mellan 0,05 och 0,95")
    if args.namn and not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.namn):
        sys.exit("--namn får bara innehålla a-z, A-Z, 0-9, - och _ (inga mellanslag eller å/ä/ö)")
    path = mosaic_path(args.namn)
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
    rows, tiles = [], []
    ms, scores = {"hela": [], "ruta": []}, {"hela": [], "ruta": []}
    print(f"Startar kameran i {'1080p' if args.hd else '4K'}. Mosaiken sparas i {path}.")
    reported = False
    try:
        with dai.Device(pipeline) as device:
            q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
            q_in = device.getInputQueue("palm_in")
            q_out = device.getOutputQueue("palm_out", maxSize=1, blocking=True)
            control = device.getInputQueue("control")
            focus = HandFocus()

            def find_palms(square, kind):
                """Kör modellen på en kvadratisk bild (128 x 128, BGR). Rutor 0-1 i den bilden."""
                frame = dai.ImgFrame()
                frame.setType(dai.ImgFrame.Type.BGR888p)
                frame.setWidth(INPUT)
                frame.setHeight(INPUT)
                frame.setData(square.transpose(2, 0, 1).flatten())
                t = time.perf_counter()
                q_in.send(frame)
                out = q_out.get()
                ms[kind].append((time.perf_counter() - t) * 1000)
                return non_max_suppression(decode_palms(out.getLayerFp16("classificators"),
                                                        out.getLayerFp16("regressors"), anchors, args.troskel))

            t0 = last = time.time()
            try:
                while time.time() - t0 < args.sekunder:
                    msg = q.get()
                    now = time.time()
                    if now - last < 0.5:                          # samma takt som skannern i 4K
                        continue
                    last = now
                    color, depth = msg["color"].getCvFrame(), msg["depth"].getFrame()
                    W, H = color.shape[1], color.shape[0]
                    region = find_near_region(depth)
                    command = focus.update(now, region)
                    if command is not None:
                        bs.send_focus(control, command, W, H)

                    # 1. Hela bilden förminskad till 128 bred, svarta kanter till en kvadrat (som förut)
                    h, top, bottom = letterbox_rows(W, H)
                    small = cv2.copyMakeBorder(cv2.resize(color, (INPUT, h), interpolation=cv2.INTER_AREA),
                                               top, bottom, 0, 0, cv2.BORDER_CONSTANT)
                    whole = [square_to_frame(p, W, H) for p in find_palms(small, "hela")]
                    scores["hela"] += [p.score for p in whole]
                    ok_whole = region is not None and any(overlaps(region, p) for p in whole)

                    # 2. Bara den blå rutan, utskuren som en kvadrat och förstorad
                    crop, box = [], None
                    if region is not None:
                        box = square_crop(region, W, H)
                        x, y, side = box
                        part = cv2.resize(color[y:y + side, x:x + side], (INPUT, INPUT), interpolation=cv2.INTER_AREA)
                        crop = [crop_to_frame(p, box, W, H) for p in find_palms(part, "ruta")]
                        scores["ruta"] += [p.score for p in crop]
                    ok_crop = region is not None and any(overlaps(region, p) for p in crop)
                    rows.append((now, region is not None, bool(whole), ok_whole, bool(crop), ok_crop))

                    if now - t0 >= 3 and len(tiles) < 200:           # efter uppstarten, högst 200 bilder
                        img = color.copy()
                        if region is not None:
                            rx, ry, rw, rh = region.to_pixels(W, H)
                            cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 8)
                        for p in whole:                              # gul, tunn: hela bilden
                            cv2.rectangle(img, (int(p.x0 * W), int(p.y0 * H)), (int(p.x1 * W), int(p.y1 * H)), (0, 230, 255), 6)
                        for p in crop:                               # grön, tjock: utskuren ruta
                            cv2.rectangle(img, (int(p.x0 * W), int(p.y0 * H)), (int(p.x1 * W), int(p.y1 * H)), (0, 220, 0), 12)
                        def said(palms):
                            return f"JA {max(p.score for p in palms):.2f}" if palms else "nej"
                        text = f"blå: {'JA' if region else 'nej'} | hela: {said(whole)} | ruta: {said(crop)}"
                        tile = cv2.resize(img, (TILE_W, TILE_H))
                        cv2.putText(tile, text.replace("å", "a"), (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                        odd = (region is not None and not ok_crop) or ok_whole != ok_crop   # rutan missade, eller oense
                        tiles.append((tile, odd))
                        print(f"  {now - t0:5.1f} s  {text}")
            except KeyboardInterrupt:
                print("\nAvbruten: sammanfattar det som hann samlas in.")
            report(rows, tiles, ms, scores, path)   # före stängningen, som kan ta några sekunder
            reported = True
            print("Stänger kameran …")
    except KeyboardInterrupt:
        if not reported:
            report(rows, tiles, ms, scores, path)


if __name__ == "__main__":
    main()
