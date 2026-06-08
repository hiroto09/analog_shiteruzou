from picamera2 import Picamera2, Preview
from time import sleep

picam2 = Picamera2()

# 正方形プレビュー設定
config = picam2.create_preview_configuration(
    main={"size": (640, 640)}
)

picam2.configure(config)

picam2.start_preview(Preview.QT)
picam2.start()

print("square preview start")

try:
    while True:
        sleep(1)

except KeyboardInterrupt:
    pass

finally:
    picam2.stop_preview()
    picam2.stop()