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
# Fristående: rör inga andra filer. Kör ALDRIG samtidigt som detect_spatial.py.
# ===============================================================
"""
barcode_scanner.py - Positionsbestämning med produkter som landmärken.

Läser en streckkod med OAK-D, slår upp produkten i kartan (GeoJSON från QGIS)
och räknar ut var användaren står: produktens position + avståndet från
djupkameran, i riktningen som hyllans "facing" anger.

Kräver:  pip install zxing-cpp numpy   (depthai finns redan i venv)
Kör:     python3 barcode_scanner.py [kartor/produkter.geojson]
"""
import json
import os
import sys
import time
from datetime import timedelta

import depthai as dai
import numpy as np
import zxingcpp

DEFAULT_MAP = "kartor/produkter.geojson"
SCAN_INTERVAL_S = 0.33      # max ~3 avkodningar per sekund (strömbudget)
CAMERA_FPS = 15
FRAME_W, FRAME_H = 1280, 720
ROI_HALF_PX = 15            # djupet tas som median i en ruta på 31x31 px runt koden
BARCODE_FORMATS = zxingcpp.BarcodeFormat.EAN13 | zxingcpp.BarcodeFormat.UPCA


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


def build_pipeline():
    pipeline = dai.Pipeline()

    cam = pipeline.create(dai.node.ColorCamera)
    cam.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam.setIspScale(2, 3)                   # 1920x1080 -> 1280x720 (skalar, beskär inte)
    cam.setVideoSize(FRAME_W, FRAME_H)
    cam.setInterleaved(False)
    cam.setFps(CAMERA_FPS)

    mono_l = pipeline.create(dai.node.MonoCamera)
    mono_r = pipeline.create(dai.node.MonoCamera)
    for mono, socket in ((mono_l, dai.CameraBoardSocket.CAM_B), (mono_r, dai.CameraBoardSocket.CAM_C)):
        mono.setBoardSocket(socket)
        mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_480_P)
        mono.setFps(CAMERA_FPS)

    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)   # djup pixel för pixel mot färgbilden
    stereo.setOutputSize(FRAME_W, FRAME_H)
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


def depth_at(depth_frame, color_shape, corners):
    """Median-djup (meter) runt streckkodens mittpunkt, eller None om djup saknas."""
    cx = sum(c.x for c in corners) / 4
    cy = sum(c.y for c in corners) / 4
    # Skala om ifall färg- och djupbild inte är exakt lika stora
    dh, dw = depth_frame.shape[:2]
    ch, cw = color_shape[:2]
    cx, cy = int(cx * dw / cw), int(cy * dh / ch)

    roi = depth_frame[max(0, cy - ROI_HALF_PX):min(dh, cy + ROI_HALF_PX + 1),
                      max(0, cx - ROI_HALF_PX):min(dw, cx + ROI_HALF_PX + 1)]
    valid = roi[roi > 0]
    return float(np.median(valid)) / 1000.0 if valid.size else None


def handle_barcode(res, color, depth, products, log, now):
    ean = normalize_ean(res.text)
    if not ean:
        return
    p = res.position
    d = depth_at(depth, color.shape, (p.top_left, p.top_right, p.bottom_right, p.bottom_left))
    if d is None:
        print(f"[{ean}] Hittad, men inget djup (för nära/för långt bort?)")
        return

    if ean not in products:
        print(f"\n[OKÄND VARA] {ean}, {d:.2f} m bort (finns inte i kartan)")
        return

    cands = products[ean]
    positions = []
    print(f"\n--- {cands[0]['namn']} ({ean}), {d:.2f} m bort ---")
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


def main():
    map_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MAP
    products = load_products(map_path)
    n_places = sum(len(v) for v in products.values())
    print(f"Karta: {len(products)} streckkoder på {n_places} platser ({map_path})")

    os.makedirs("logs", exist_ok=True)
    log_path = f"logs/scan_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    with dai.Device(build_pipeline()) as device, open(log_path, "a", encoding="utf-8") as log:
        q = device.getOutputQueue(name="out", maxSize=4, blocking=False)
        print(f"Söker efter streckkoder (max ~{1 / SCAN_INTERVAL_S:.0f}/s). Loggar till {log_path}. Ctrl+C avslutar.")
        last_scan = 0.0
        try:
            while True:
                msg = q.get()
                now = time.time()
                # Begränsa ALLA avkodningar, även när ingen kod syns (CPU = ström)
                if now - last_scan < SCAN_INTERVAL_S:
                    continue
                last_scan = now

                color = msg["color"].getCvFrame()
                depth = msg["depth"].getFrame()   # uint16, millimeter
                for res in zxingcpp.read_barcodes(color, formats=BARCODE_FORMATS):
                    handle_barcode(res, color, depth, products, log, now)
        except KeyboardInterrupt:
            print("\nAvslutar.")


if __name__ == "__main__":
    main()
