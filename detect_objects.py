import depthai as dai
import blobconverter
import time

# Listan på objekt
labelMap = ["bakgrund", "flygplan", "cykel", "fagel", "bat", "flaska", "buss", "bil", "katt", "stol", "ko", "matbord", "hund", "hast", "motorcykel", "person", "krukvat", "far", "soffa", "tag", "monitor"]

pipeline = dai.Pipeline()

# 1. Kamera-inställningar
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(300, 300)
camRgb.setInterleaved(False)
camRgb.setFps(40)

# 2. AI-motor (MobileNet)
nn = pipeline.create(dai.node.MobileNetDetectionNetwork)
nn.setConfidenceThreshold(0.5)
nn.setBlobPath(blobconverter.from_zoo(name="mobilenet-ssd", shaves=5))

# 3. Koppla Kamera -> AI
camRgb.preview.link(nn.input)

# 4. Skapa utgång för terminalen
xoutNn = pipeline.create(dai.node.XLinkOut)
xoutNn.setStreamName("detektioner")
nn.out.link(xoutNn.input)

# 5. Kör!
try:
    with dai.Device(pipeline) as device:
        qDet = device.getOutputQueue(name="detektioner", maxSize=4, blocking=False)
        print("\n🚀 AI-MOTORN ÄR IGÅNG! Nu börjar jag analysera världen...")
        
        while True:
            inDet = qDet.get()
            detections = inDet.detections
            if len(detections) > 0:
                for detection in detections:
                    label = labelMap[detection.label]
                    conf = int(detection.confidence * 100)
                    print(f"👁️ Jag ser: {label} ({conf}%)")
            time.sleep(0.1)
except Exception as e:
    print(f"❌ Ett fel uppstod: {e}")
