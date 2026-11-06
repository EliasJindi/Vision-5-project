# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Tar EN bild och sparar den i logs/sikte.jpg, så att man ser vad kameran ser innan ett test.
# 6/11: kameran på huvudet pekade mot taket eller för högt i flera körningar, och varan hamnade
# vid bildens kant. Håll varan där du tänker hålla den: den ska synas mitt i bilden.
# Kör utan att skannern är igång:  python3 tools/sikte.py
# =========================================================================
import os
import time

import cv2
import depthai as dai

SETTLE_S = 3.0   # låt autofokus och ljus ställa in sig innan bilden sparas


def main():
    p = dai.Pipeline()
    cam = p.create(dai.node.ColorCamera)
    cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    out = p.create(dai.node.XLinkOut)
    out.setStreamName("rgb")
    cam.video.link(out.input)
    os.makedirs("logs", exist_ok=True)
    with dai.Device(p) as d:
        q = d.getOutputQueue("rgb", 4, False)
        t0 = time.time()
        frame = None
        while time.time() - t0 < SETTLE_S or frame is None:
            frame = q.get().getCvFrame()
        cv2.imwrite("logs/sikte.jpg", frame)
        print(f"Sparat: logs/sikte.jpg (USB: {d.getUsbSpeed().name}). Varan ska synas mitt i bilden.")


if __name__ == "__main__":
    main()
