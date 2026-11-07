# ===================== NY FIL AV CLAUDE (2026-11-07) =====================
# Mätverktyg för Elias idé 7/11: kan kameran se ATT det finns en streckkod i handen innan den går
# att läsa, och säga "vrid varan" när det inte finns någon? OpenCV:s färdiga streckkodsdetektor
# (cv2.barcode.BarcodeDetector) hittar var en kod är utan att avkoda den. Verktyget kör skannerns
# handläge (linsen efter handens avstånd), och för varje bild jämförs: hittade detektorn en kod i
# handrutan, och kunde zxing läsa den? Sparar en mosaik i logs/streckkod.jpg (blå = handen,
# gul = detektorns kod) och skriver ut tiden detektorn tar. Ändrar ingenting i skannern.
#   python3 tools/streckkod.py              (4K, 30 s)
#   python3 tools/streckkod.py --sekunder 45 --skala 0.5   (detektorn på halv upplösning: snabbare?)
#   clear && sleep 15 && python3 tools/streckkod.py      (15 s att ställa sig först). Ctrl+C avslutar och sammanfattar.
# Mosaiken tar alltid med bilderna där detektorn eller zxing hittade något (7/11: de kom annars inte med).
# Zoom (7/11, mätning): när detektorn ser en kod som zxing inte läste skärs koden ut, förstoras 2 gånger
# och läses igen. "Räddade" visar hur ofta det hjälper, och vilka koder som lästes (felläsningar?).
# Vrid varan under tiden: koden synlig ibland, bortvänd ibland, så syns både träffar och falsklarm.
# =========================================================================
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # projektets rot

TILE_W, TILE_H = 480, 270


def quads(result, dx=0, dy=0, scale=1.0):
    """detect() ger (ok, punkter) med punkterna som N x 4 x 2, eller None. Till hela bildens koordinater."""
    ok, points = result
    if not ok or points is None:
        return []
    return [[(float(x) / scale + dx, float(y) / scale + dy) for x, y in quad] for quad in points]


def zoom_box(quad, width, height, margin=0.3):
    """Rutan runt en kod (fyra hörn) med marginal i förhållande till kodens längsta sida, inom bilden."""
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    m = margin * max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    return (max(0, int(min(xs) - m)), max(0, int(min(ys) - m)),
            min(width, int(max(xs) + m) + 1), min(height, int(max(ys) + m) + 1))


def pick_tiles(flags, n=16):
    """
    Vilka bilder som kommer med i mosaiken (index i tidsordning). Alla där detektorn eller zxing
    hittade något kommer med först (det är dem vi vill granska), resten fylls jämnt utspritt.
    flags: [bool] per bild, sant om något hittades.
    """
    hits = [i for i, f in enumerate(flags) if f][:n]
    rest = [i for i, f in enumerate(flags) if not f]
    room = n - len(hits)
    if room > 0 and rest:
        k = min(room, len(rest))
        hits += [rest[round(j * (len(rest) - 1) / max(1, k - 1))] for j in range(k)]
    return sorted(set(hits))


def summarize(rows):
    """rows: [(hand, upptäckt, läst, räddad)]. Räknar det som avgör om detektorn är användbar."""
    with_hand = [r for r in rows if r[0]]
    return {
        "bilder": len(rows),
        "med_hand": len(with_hand),
        "upptackt": sum(1 for _, found, _, _ in with_hand if found),
        "last": sum(1 for _, _, read, _ in with_hand if read),
        "upptackt_ej_last": sum(1 for _, found, read, _ in with_hand if found and not read),   # "håll stilla"
        "last_ej_upptackt": sum(1 for _, found, read, _ in with_hand if read and not found),   # detektorn missade
        "raddade": sum(1 for _, found, read, saved in with_hand if found and not read and saved),   # zoom hjälpte
    }


def report(rows, tiles, rescued_codes, ms, skala):
    """Sammanfattning och mosaik. Anropas innan kameran stängs (7/11: Ctrl+C under stängningen gav inget)."""
    import cv2
    import numpy as np
    os.makedirs("logs", exist_ok=True)
    stats = summarize(rows)
    picked = [tiles[i][0] for i in pick_tiles([hit for _, hit in tiles])]   # bilder med fynd först
    while picked and len(picked) % 4:
        picked.append(np.zeros((TILE_H, TILE_W, 3), np.uint8))
    if picked:
        cv2.imwrite("logs/streckkod.jpg", np.vstack([np.hstack(picked[i:i + 4]) for i in range(0, len(picked), 4)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"\nKlart: logs/streckkod.jpg. {stats['bilder']} bilder, handen i {stats['med_hand']}.")
    print(f"  Detektorn såg en kod i {stats['upptackt']} av dem, zxing läste en kod i {stats['last']}.")
    print(f"  Sedd men inte läst (då skulle rösten säga \"håll stilla\"): {stats['upptackt_ej_last']}")
    print(f"  Läst men inte sedd (detektorn missade): {stats['last_ej_upptackt']}")
    print(f"  Räddade med zoom (utskuren kod, 2 gånger större): {stats['raddade']} av {stats['upptackt_ej_last']}")
    if rescued_codes:
        counts = {c: rescued_codes.count(c) for c in sorted(set(rescued_codes))}
        print("  Koder som zoomen läste: " + ", ".join(f"{c} ({n})" for c, n in counts.items())
              + "  <- kontrollera att det är varans riktiga kod")
    if ms:
        print(f"  Detektorn: median {sorted(ms)[len(ms) // 2]:.0f} ms per bild (max {max(ms):.0f} ms), skala {skala}")


def main():
    import cv2
    import depthai as dai
    import numpy as np

    import barcode_scanner as bs
    from hand_region import HandFocus, find_near_region

    ap = argparse.ArgumentParser(description="Ser OpenCV:s detektor streckkoden i handen innan den går att läsa?")
    ap.add_argument("--1080p", dest="hd", action="store_true", help="1080p i stället för 4K")
    ap.add_argument("--sekunder", type=float, default=30.0)
    ap.add_argument("--skala", type=float, default=1.0, help="detektorn på nedskalad handruta (t.ex. 0.5)")
    args = ap.parse_args()
    if not 0.1 <= args.skala <= 1.0:
        sys.exit("--skala ska ligga mellan 0,1 och 1,0")
    detector = cv2.barcode.BarcodeDetector()
    os.makedirs("logs", exist_ok=True)
    rows, ms, tiles, rescued_codes = [], [], [], []
    print("Startar kameran. Håll fram varan och vrid den: koden synlig ibland, bortvänd ibland.")
    reported = False
    try:
        with dai.Device(bs.build_pipeline(uhd=not args.hd, hand=True)) as device:
            q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
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
                    crop = focus.crop(now)
                    found = []
                    if crop is not None:
                        x, y, w, h = crop.to_pixels(color.shape[1], color.shape[0])
                        part = color[y:y + h, x:x + w]
                        if args.skala < 1.0:
                            part = cv2.resize(part, None, fx=args.skala, fy=args.skala)
                        t = time.perf_counter()
                        found = quads(detector.detect(part), x, y, args.skala)
                        ms.append((time.perf_counter() - t) * 1000)
                    results, _ = bs.decode_frame(color, crop)
                    saved = []
                    if found and not results:                    # zoom: skär ut koden, förstora, läs igen
                        for qd in found:
                            x0, y0, x1, y1 = zoom_box(qd, color.shape[1], color.shape[0])
                            big = cv2.resize(color[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                            saved += [r.text for r in bs.zxingcpp.read_barcodes(big, formats=bs.BARCODE_FORMATS)]
                    rescued_codes += saved
                    rows.append((region is not None, bool(found), bool(results), bool(saved)))
                    if now - t0 >= 3 and len(tiles) < 200:           # efter uppstarten, högst 200 bilder
                        img = color.copy()
                        if region is not None:
                            rx, ry, rw, rh = region.to_pixels(img.shape[1], img.shape[0])
                            cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (255, 128, 0), 8)
                        for qd in found:
                            cv2.polylines(img, [np.array(qd, np.int32)], True, (0, 255, 255), 8)
                        text = (f"{'hand' if region else 'ingen hand'} | detektor: {'JA' if found else 'nej'} | "
                                f"last: {'JA' if results else 'nej'}{' | zoom: JA' if saved else ''}")
                        tile = cv2.resize(img, (TILE_W, TILE_H))
                        cv2.putText(tile, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
                        tiles.append((tile, bool(found or results or saved)))
                        print(f"  {now - t0:5.1f} s  {text}")
            except KeyboardInterrupt:
                print("\nAvbruten: sammanfattar det som hann samlas in.")
            report(rows, tiles, rescued_codes, ms, args.skala)   # före stängningen, som kan ta några sekunder
            reported = True
            print("Stänger kameran …")
    except KeyboardInterrupt:
        if not reported:
            report(rows, tiles, rescued_codes, ms, args.skala)


if __name__ == "__main__":
    main()
