from picamera2 import Picamera2, Preview
from time import sleep

picam2 = Picamera2()

# QTプレビュー
picam2.start_preview(Preview.QT)

picam2.start()

print("camera preview start")

try:
    while True:
        sleep(1)

except KeyboardInterrupt:
    pass

finally:
    picam2.stop_preview()
    picam2.stop()