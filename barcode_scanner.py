# ===================== NY FIL (2026-10-13) =====================
# Grund: Geminis utkast. Granskad och rättad av Claude:
#  1. time.timedelta -> datetime.timedelta (kraschade när pipelinen byggdes)
#  2. msg.get("color") -> msg["color"] (MessageGroup saknar .get(), kraschade)
#  3. Hastighetsbegränsningen gäller ALLA bildrutor, inte bara de med kod
#     (annars avkodas 30 bildrutor/s på full CPU -> strömproblem)
#  4. Position läses från kartans GEOMETRI, inte attributen x/y
#     (flyttar man en punkt i QGIS uppdateras inte attributen)
#  5. Avbryter med tydligt fel om kartan inte kan läsas
#  6. setVideoSize(1280, 720) efter setIspScale, 15 fps, bara EAN-13/UPC-A
# Runda 2 (efter första testet på Pi: koderna lästes men djupet saknades):
#  7. Extended disparity: minsta mätbara avstånd ca halveras (OAK-D Lite ~35 cm -> ~20 cm)
#  8. Färgbilden i 1080p så att koder kan läsas längre bort, där djupet fungerar
#  9. Reservruta: om mitten saknar djup används hela streckkodens yta
# 10. Diagnostik som visar VARFÖR djupet saknas
# 11. --diag: sparar en bild varannan sekund + skriver ut ljus och skärpa
#     (för att se varför koder inte läses, utan att flytta sig ur position)
# 12. --4k: färgbilden i 3840x2160 (dubbelt så många pixlar per streck) med
#     5 fps och 2 avkodningar/s. Kräver USB3, varnar annars.
# Fristående: rör inga andra filer. Kör ALDRIG samtidigt som detect_spatial.py.
# ===============================================================
"""
barcode_scanner.py - Positionsbestämning med produkter som landmärken.

Läser en streckkod med OAK-D, slår upp produkten i kartan (GeoJSON från QGIS)
och räknar ut var användaren står: produktens position + avståndet från
djupkameran, i riktningen som hyllans "facing" anger.

Kräver:  pip install zxing-cpp numpy   (depthai finns redan i venv)
Kör:     python3 barcode_scanner.py [kartor/produkter.geojson] [--diag] [--4k]
         --diag sparar logs/snapshots/*.jpg varannan sekund och visar ljus/skärpa
         --4k   läser i 3840x2160 (längre läsavstånd, mer CPU/USB)
"""
import argparse
import json
import os
import sys
import time
from datetime import timedelta

import cv2
import depthai as dai
import numpy as np
import zxingcpp

DEFAULT_MAP = "kartor/produkter.geojson"
SCAN_INTERVAL_S = 0.33      # max ~3 avkodningar per sekund (strömbudget)
CAMERA_FPS = 15
COLOR_W, COLOR_H = 1920, 1080   # full upplösning: koder går att läsa längre bort
# --4k: dubbelt så många pixlar per streck. 4K-video kräver mycket USB-bandbredd,
# därför lägre fps, och avkodningen av en 4K-bild tar längre tid -> färre per sekund.
UHD_W, UHD_H = 3840, 2160
UHD_FPS = 5
UHD_SCAN_INTERVAL_S = 0.5
DEPTH_W, DEPTH_H = 1280, 720     # djupbilden kan vara mindre, koordinaterna skalas om
ROI_HALF_PX = 15            # djupet tas som median i en ruta på 31x31 px runt koden
MIN_VALID_PX = 20           # minst så många giltiga djuppixlar för att lita på medianen
DIAG_INTERVAL_S = 2.0      # --diag: en bild varannan sekund
DIAG_MAX_IMAGES = 60       # --diag: sluta spara efter så många (skonar SD-kortet)
BARCODE_FORMATS = (zxingcpp.BarcodeFormat.EAN13, zxingcpp.BarcodeFormat.UPCA)


def normalize_ean(code):
    """
    Returnerar en giltig 13-siffrig EAN, eller None.
    En 12-siffrig UPC-A (783935132243) blir EAN-13 med inledande nolla (0783935132243).
    """
    code = str(code).strip()
    if not code.isdigit() or len(code) not in (12, 13):
        return None
    code = code.zfill(13)
    total = sum(int(code[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
    return code if (10 - total % 10) % 10 == int(code[12]) else None


def load_products(path):
    """{ean: [kandidat, ...]} - samma EAN kan finnas på flera platser."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"❌ Kunde inte läsa kartan {path}: {e}")

    products = {}
    for feat in data.get("features", []):
        p = feat.get("properties", {})
        ean = normalize_ean(p.get("ean", ""))
        if not ean:
            print(f"⚠️  Hoppar över {p.get('namn', '?')}: ogiltig streckkod {p.get('ean')!r}")
            continue
        x, y = feat["geometry"]["coordinates"][:2]   # geometrin är sanningen, inte attributen
        products.setdefault(ean, []).append({
            "namn": p.get("namn", "?"),
            "x": float(x),
            "y": float(y),
            "ligger_pa": p.get("ligger_pa", "okänd plats"),
            "facing": p.get("facing", ""),
        })

    if not products:
        sys.exit(f"❌ Inga giltiga produkter i {path}")
    return products


def user_position(cand, d):
    """Användaren står d meter framför produkten, på hyllans framsida."""
    if cand["facing"] == "+x":
        return cand["x"] + d, cand["y"]
    if cand["facing"] == "-x":
        return cand["x"] - d, cand["y"]
    if cand["facing"] == "+y":
        return cand["x"], cand["y"] + d
    if cand["facing"] == "-y":
        return cand["x"], cand["y"] - d
    return None


def build_pipeline(uhd=False):
    pipeline = dai.Pipeline()
    fps = UHD_FPS if uhd else CAMERA_FPS

    cam = pipeline.create(dai.node.ColorCamera)
    cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    if uhd:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_4_K)
        cam.setVideoSize(UHD_W, UHD_H)
    else:
        cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        cam.setVideoSize(COLOR_W, COLOR_H)
    cam.setInterleaved(False)
    cam.setFps(fps)

    mono_l = pipeline.create(dai.node.MonoCamera)
    mono_r = pipeline.create(dai.node.MonoCamera)
    for mono, socket in ((mono_l, dai.CameraBoardSocket.CAM_B), (mono_r, dai.CameraBoardSocket.CAM_C)):
        mono.setBoardSocket(socket)
        mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
        mono.setFps(fps)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    # Streckkoder läses nära kameran. Utan detta saknas djup närmare än ca 35 cm.
    stereo.setExtendedDisparity(True)
    stereo.setSubpixel(False)          # krävs tillsammans med extended disparity
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)   # djup pixel för pixel mot färgbilden
    stereo.setOutputSize(DEPTH_W, DEPTH_H)
    mono_l.out.link(stereo.left)
    mono_r.out.link(stereo.right)

    # Sync parar ihop färg- och djupbild från samma ögonblick
    sync = pipeline.create(dai.node.Sync)
    sync.setSyncThreshold(timedelta(milliseconds=50))
    cam.video.link(sync.inputs["color"])
    stereo.depth.link(sync.inputs["depth"])

    xout = pipeline.create(dai.node.XLinkOut)
    xout.setStreamName("out")
    sync.out.link(xout.input)
    return pipeline


def _median_m(region):
    valid = region[region > 0]
    return (float(np.median(valid)) / 1000.0 if valid.size >= MIN_VALID_PX else None), int(valid.size)


def depth_at(depth_frame, color_shape, corners):
    """
    Median-djup (meter) vid streckkoden. Returnerar (avstånd eller None, förklaring).
    Försöker först en liten ruta i mitten, sedan hela kodens yta (+50 % marginal).
    """
    dh, dw = depth_frame.shape[:2]
    ch, cw = color_shape[:2]
    sx, sy = dw / cw, dh / ch            # färgbild -> djupbild
    xs = [c.x * sx for c in corners]
    ys = [c.y * sy for c in corners]
    cx, cy = int(sum(xs) / 4), int(sum(ys) / 4)

    d, n_center = _median_m(depth_frame[max(0, cy - ROI_HALF_PX):min(dh, cy + ROI_HALF_PX + 1),
                                        max(0, cx - ROI_HALF_PX):min(dw, cx + ROI_HALF_PX + 1)])
    if d is not None:
        return d, "mitten"

    # Reserv: hela streckkodens yta med marginal
    mx = max(10, int((max(xs) - min(xs)) * 0.5))
    my = max(10, int((max(ys) - min(ys)) * 0.5))
    x0, x1 = max(0, int(min(xs)) - mx), min(dw, int(max(xs)) + mx + 1)
    y0, y1 = max(0, int(min(ys)) - my), min(dh, int(max(ys)) + my + 1)
    d, n_box = _median_m(depth_frame[y0:y1, x0:x1])
    if d is not None:
        return d, "kodens yta"

    # Diagnostik: saknas djup bara här, eller i hela bilden?
    whole = float(np.count_nonzero(depth_frame)) / depth_frame.size
    if whole < 0.05:
        why = f"nästan inget djup i hela bilden ({whole:.0%}), kameran ser troligen för nära eller för mörkt"
    else:
        why = (f"djup finns i {whole:.0%} av bilden men inte vid koden "
               f"({n_center}+{n_box} giltiga px). För nära (<~20 cm) eller blank yta?")
    return None, why


def handle_barcode(res, color, depth, products, log, now):
    ean = normalize_ean(res.text)
    if not ean:
        return
    p = res.position
    d, how = depth_at(depth, color.shape, (p.top_left, p.top_right, p.bottom_right, p.bottom_left))
    if d is None:
        print(f"[{ean}] Hittad, men inget djup: {how}")
        log.write(json.dumps({"t": round(now, 3), "ean": ean, "distance_m": None, "why": how},
                             ensure_ascii=False) + "\n")
        log.flush()
        return

    if ean not in products:
        print(f"\n[OKÄND VARA] {ean}, {d:.2f} m bort (finns inte i kartan)")
        return

    cands = products[ean]
    positions = []
    print(f"\n--- {cands[0]['namn']} ({ean}), {d:.2f} m bort (djup från {how}) ---")
    for c in cands:
        pos = user_position(c, d)
        if pos is None:
            print(f"   ⚠️  {c['ligger_pa']}: okänd facing {c['facing']!r}")
            continue
        positions.append({"x": round(pos[0], 3), "y": round(pos[1], 3), "ligger_pa": c["ligger_pa"]})
        print(f"   📍 Du står vid x={pos[0]:.2f}, y={pos[1]:.2f} (framför {c['ligger_pa']})")
    ambiguous = len(positions) > 1
    if ambiguous:
        print(f"   ⚠️  Tvetydigt: varan finns på {len(positions)} platser")

    log.write(json.dumps({
        "t": round(now, 3), "ean": ean, "namn": cands[0]["namn"], "format": str(res.format),
        "distance_m": round(d, 3), "candidates": positions, "ambiguous": ambiguous,
    }, ensure_ascii=False) + "\n")
    log.flush()
    os.fsync(log.fileno())   # överlever strömavbrott


def diagnose(color, results, n_saved, folder):
    """Ljus och skärpa i bilden, och sparar en märkt bild. Returnerar en statusrad."""
    gray = cv2.cvtColor(cv2.resize(color, (960, 540)), cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())                              # 0 = svart, 255 = vitt
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())     # lågt = suddigt
    status = (f"📷 ljus {brightness:3.0f}/255 ({'mörkt' if brightness < 60 else 'ok'})  "
              f"skärpa {sharpness:5.0f} ({'suddigt' if sharpness < 50 else 'ok'})  "
              f"koder: {[r.text for r in results] or 'inga'}")

    if n_saved < DIAG_MAX_IMAGES:
        img = color.copy()
        for r in results:
            pts = np.array([[c.x, c.y] for c in (r.position.top_left, r.position.top_right,
                                                 r.position.bottom_right, r.position.bottom_left)], np.int32)
            cv2.polylines(img, [pts], True, (0, 255, 0), 4)
        # OpenCV kan inte rita å/ä/ö
        ascii_status = status.replace("📷 ", "").translate(str.maketrans("åäöÅÄÖ", "aaoAAO"))
        cv2.putText(img, ascii_status, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        path = os.path.join(folder, f"snap_{n_saved + 1:03d}_{time.strftime('%H%M%S')}.jpg")
        cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        status += f"  → {path}"
    return status


def main():
    ap = argparse.ArgumentParser(description="Position från streckkoder (produkter som landmärken)")
    ap.add_argument("karta", nargs="?", default=DEFAULT_MAP)
    ap.add_argument("--diag", action="store_true", help="spara bilder och visa ljus/skärpa varannan sekund")
    ap.add_argument("--4k", dest="uhd", action="store_true", help="läs i 3840x2160 (längre läsavstånd)")
    args = ap.parse_args()
    map_path = args.karta
    products = load_products(map_path)
    n_places = sum(len(v) for v in products.values())
    print(f"Karta: {len(products)} streckkoder på {n_places} platser ({map_path})")

    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/scan_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    scan_interval = UHD_SCAN_INTERVAL_S if args.uhd else SCAN_INTERVAL_S
    with dai.Device(build_pipeline(uhd=args.uhd)) as device, open(log_path, "a", encoding="utf-8") as log:
        usb = device.getUsbSpeed()
        print(f"Kamera: {'4K 3840x2160 @ ' + str(UHD_FPS) if args.uhd else '1080p @ ' + str(CAMERA_FPS)} fps, USB {usb.name}")
        if args.uhd and usb not in (dai.UsbSpeed.SUPER, dai.UsbSpeed.SUPER_PLUS):
            print("⚠️  4K kräver USB3 (blå port). Med USB2 kan bilden hacka eller utebli.")
        q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
        print(f"Söker efter streckkoder (max ~{1 / scan_interval:.0f}/s). Loggar till {log_path}. Ctrl+C avslutar.")
        last_scan = last_diag = 0.0
        n_saved = 0
        diag_dir = "logs/snapshots"
        if args.diag:
            os.makedirs(diag_dir, exist_ok=True)
            print(f"Diagnostik PÅ: bild var {DIAG_INTERVAL_S:.0f}:e sekund till {diag_dir}/ (max {DIAG_MAX_IMAGES})")
        try:
            while True:
                msg = q.get()
                now = time.time()
                # Begränsa ALLA avkodningar, även när ingen kod syns (CPU = ström)
                if now - last_scan < scan_interval:
                    continue
                last_scan = now

                color = msg["color"].getCvFrame()
                depth = msg["depth"].getFrame()   # uint16, millimeter
                results = zxingcpp.read_barcodes(color, formats=BARCODE_FORMATS)
                for res in results:
                    handle_barcode(res, color, depth, products, log, now)

                if args.diag and now - last_diag >= DIAG_INTERVAL_S:
                    last_diag = now
                    print(diagnose(color, results, n_saved, diag_dir))
                    n_saved += 1
        except KeyboardInterrupt:
            print("\nAvslutar.")


if __name__ == "__main__":
    main()
