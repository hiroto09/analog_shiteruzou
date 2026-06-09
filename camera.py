from picamera2 import Picamera2
import tensorflow as tf
import numpy as np
import cv2
import time

# ==========================
# TFLiteモデル読み込み
# ==========================

interpreter = tf.lite.Interpreter(
    model_path="game_classifier_analog_v1.tflite"
)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# ==========================
# クラス名
# ==========================

CLASS_NAMES = [
    "nanimoshitenai",
    "ayaturi",
    "katan"
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
# 推論関数
# ==========================

def predict_frame(frame):

    # BGRA → RGB
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

    img = cv2.resize(frame, (224, 224))

    img = img.astype(np.float32) / 255.0

    img = np.expand_dims(img, axis=0)

    interpreter.set_tensor(
        input_details[0]["index"],
        img
    )

    interpreter.invoke()

    pred = interpreter.get_tensor(
        output_details[0]["index"]
    )

    idx = np.argmax(pred)

    game = CLASS_NAMES[idx]

    score = float(pred[0][idx])

    return game, score

# ==========================
# 20秒ごと推論
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