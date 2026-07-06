from picamera2 import Picamera2
import tensorflow as tf
import numpy as np
import cv2
import time
from collections import Counter

import requests
import threading
import os
from dotenv import load_dotenv
from datetime import datetime


# ==========================
# .env 読み込み
# ==========================

load_dotenv()

API_URL = os.getenv("API_URL")

# HTTPセッション使い回し
session = requests.Session()


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
    frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGRA2RGB
    )

    # 224×224にリサイズ
    img = cv2.resize(
        frame,
        (224, 224)
    )

    # 正規化
    img = img.astype(np.float32) / 255.0

    # バッチ次元追加
    img = np.expand_dims(
        img,
        axis=0
    )

    # モデルへ入力
    interpreter.set_tensor(
        input_details[0]["index"],
        img
    )

    # 推論
    interpreter.invoke()

    pred = interpreter.get_tensor(
        output_details[0]["index"]
    )

    # 最大確率のインデックス
    idx = np.argmax(pred)

    # 文字列に変換して返す
    game = str(idx)

    confidence = float(np.max(pred))

    return game, confidence


# ==========================
# SERVER送信
# ==========================

def send_to_server(send_id):

    try:

        print("📡 送信:", send_id)

        res = session.post(
            API_URL,
            json={
                "tag_id": send_id,
                "timestamp": datetime.now().isoformat()
            },
            timeout=3
        )

        print("✅ status:", res.status_code)

    except Exception as e:

        print("❌ 送信エラー:", e)


# ==========================
# 2分間で9回推論
# ==========================

INTERVAL = 120 / 9   # 約13.3秒


try:

    while True:

        results = []

        for i in range(9):

            # カメラ取得
            frame = picam2.capture_array()

            # 推論
            game, conf = predict_frame(frame)

            # 結果保存
            results.append(game)


            # 最後は待たない
            if i < 8:

                time.sleep(INTERVAL)

        # =====================
        # 最頻値取得
        # =====================

        counter = Counter(results)

        send_id = counter.most_common(1)[0][0]

        print("推論結果:", send_id)


        # =====================
        # 非同期送信
        # =====================

        threading.Thread(
            target=send_to_server,
            args=(send_id,),
            daemon=True
        ).start()


except KeyboardInterrupt:

    print("\n終了します")


finally:

    picam2.stop()

    print("camera stopped")