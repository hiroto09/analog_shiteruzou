from picamera2 import Picamera2
from time import sleep

picam2 = Picamera2()
picam2.start()

sleep(2)

picam2.capture_file("test.jpg")
print("saved")