from picamera2 import Picamera2
import tensorflow as tf
import numpy as np
import cv2
import time

# ==========================
# モデル読み込み
# ==========================

model = tf.keras.models.load_model(
    "game_classifier_analog_v1_fixed.h5",
    compile=False
)

CLASS_NAMES = [
    "class1",
    "class2",
    "class3"
]

# ==========================
# カメラ初期化
# ==========================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 640)}
)

picam2.configure(config)
picam2.start()

print("camera started")

# ==========================
# 推定関数
# ==========================

def predict_frame(frame):

    img = cv2.resize(frame, (128, 128))

    img = img.astype(np.float32) / 255.0

    img = np.expand_dims(img, axis=0)

    pred = model.predict(img, verbose=0)

    idx = np.argmax(pred)

    game = CLASS_NAMES[idx]

    score = float(pred[0][idx])

    return game, score

# ==========================
# 20秒ごとに推定
# ==========================

try:
    while True:

        frame = picam2.capture_array()

        game, score = predict_frame(frame)

        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"{game} ({score:.1%})"
        )

        time.sleep(20)

except KeyboardInterrupt:
    pass

finally:
    picam2.stop()