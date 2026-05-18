from picamera2 import Picamera2
from picamera2.preview import Preview
from time import sleep

picam2 = Picamera2()

# プレビュー開始
picam2.start_preview(Preview.QTGL)

# カメラ開始
picam2.start()

print("camera preview start")

try:
    while True:
        sleep(1)

except KeyboardInterrupt:
    print("stop")

finally:
    picam2.stop_preview()
    picam2.stop()