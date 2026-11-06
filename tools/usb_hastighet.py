# ===================== NY FIL AV CLAUDE (2026-11-06) =====================
# Visar om kameran går på USB 3 (SUPER) eller USB 2 (HIGH). 6/11: kameran gick på USB 2 tills
# USB-C-kontakten vid kameran vändes. På USB 2 kommer bara hälften av bilderna fram och 4K kan krascha.
# Kör utan att skannern är igång:  python3 tools/usb_hastighet.py
# =========================================================================
import depthai as dai


def main():
    p = dai.Pipeline()
    cam = p.create(dai.node.ColorCamera)
    out = p.create(dai.node.XLinkOut)
    out.setStreamName("x")
    cam.video.link(out.input)
    with dai.Device(p) as d:
        speed = d.getUsbSpeed().name
    hint = "" if speed in ("SUPER", "SUPER_PLUS") else "  (USB 2: vänd USB-C-kontakten vid kameran och kör igen)"
    print(f"USB: {speed}{hint}")


if __name__ == "__main__":
    main()
