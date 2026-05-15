import depthai as dai

# Skapa en pipeline
pipeline = dai.Pipeline()

# Skapa färgkameran (denna nod finns i v2!)
camRgb = pipeline.create(dai.node.ColorCamera)
camRgb.setPreviewSize(300, 300)
camRgb.setInterleaved(False)

# Starta enheten och kör pipelinen
try:
    with dai.Device(pipeline) as device:
        print("\n" + "="*40)
        print("✅ SUCCESS! Den stabila v2-motorn lever!")
        print(f"Kopplad till: {device.getDeviceName()}")
        print(f"USB-hastighet: {device.getUsbSpeed()}")
        print("="*40 + "\n")
except Exception as e:
    print(f"\n❌ Kunde inte starta kameran: {e}")
