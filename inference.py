from picamera2 import Picamera2
import tensorflow as tf
import numpy as np
import cv2
import time
from collections import Counter

# ==========================
# TFLiteモデル読み込み
# ==========================

interpreter = tf.lite.Interpreter(
    model_path="game_classifier_analog_v2.tflite"
)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# ==========================
# クラス名
# ==========================

CLASS_MAP = {
    0: "何もしてない",
    1: "操り人形",
    2: "カタン",
    3: "麻雀",
}

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

    game = CLASS_MAP.get(idx, "Unknown")

    return game


# ==========================
# 2分間で9回推論
# ==========================

INTERVAL = 120 / 9  # 約13.3秒

try:

    while True:

        results = []

        print("=== 推定開始 ===")

        for i in range(9):

            frame = picam2.capture_array()

            game = predict_frame(frame)

            results.append(game)

            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"{i+1}/9 : {game}"
            )

            # 最後は待たない
            if i < 8:
                time.sleep(INTERVAL)

        # 最頻値を取得
        counter = Counter(results)

        final_game = counter.most_common(1)[0][0]

        print("\n====================")
        print("各推定結果:", results)
        print("最終推定結果:", final_game)
        print("====================\n")

except KeyboardInterrupt:
    pass

finally:
    picam2.stop()