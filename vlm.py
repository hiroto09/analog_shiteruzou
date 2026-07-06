from picamera2 import Picamera2
import cv2
import numpy as np
import time
import os
import threading
import requests

from dotenv import load_dotenv
from datetime import datetime

from google import genai
from PIL import Image

# ==========================================
# .env 読み込み
# ==========================================

load_dotenv()

API_URL = os.getenv("API_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# HTTP Session
# ==========================================

session = requests.Session()

# ==========================================
# Gemini
# ==========================================

client = genai.Client(
    api_key=GEMINI_API_KEY
)

# ==========================================
# Camera
# ==========================================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (640, 640)}
)

picam2.configure(config)
picam2.start()

print("camera started")

time.sleep(2)

# ==========================================
# 差分判定
# ==========================================

def has_changed(prev_frame, current_frame, threshold=5000):

    prev_gray = cv2.cvtColor(
        prev_frame,
        cv2.COLOR_BGRA2GRAY
    )

    curr_gray = cv2.cvtColor(
        current_frame,
        cv2.COLOR_BGRA2GRAY
    )

    diff = cv2.absdiff(
        prev_gray,
        curr_gray
    )

    _, diff = cv2.threshold(
        diff,
        30,
        255,
        cv2.THRESH_BINARY
    )

    changed_pixels = np.count_nonzero(diff)

    print("Changed Pixels :", changed_pixels)

    return changed_pixels > threshold


# ==========================================
# Gemini 推論
# ==========================================

def recognize_boardgame(image_path):

    image = Image.open(image_path)

    response = client.models.generate_content(

        model="gemini-2.5-flash-lite",

        contents=[
            image,
            """
画像に写っているボードゲームを推定してください。

以下の候補から最も近いものを1つ選んでください。

候補
・何もしていない
・カタカナーシ
・チェス
・モダンアート
・マーダーミステリー
・UIかるた
・カラーコードかるた
・Linuxコマンドかるた
・トランプ
・お邪魔者
・お邪魔者2
・カタン（スタンダード）
・カタン（大航海時代）
・キャンプ場の殺人鬼
・コヨーテ
・犯人は踊る
・犯人は踊る3
・ファットプロジェクト
・プログラム言語神経衰弱
・テストプレイなんてしてないよ
・まじかる★ベーカリー
・ito
・人狼
・プロポーズ
・麻雀
・宝石の煌めき

候補にない場合は
「何もしていない」
と回答してください。

回答は次の形式のみで出力してください。

タイトル: ○○
信頼度: ○%

"""
        ]

    )

    return response.text


# ==========================================
# API送信
# ==========================================

def send_to_server(result):

    try:

        print("送信開始")

        response = session.post(

            API_URL,

            json={
                "result": result,
                "timestamp": datetime.now().isoformat()
            },

            timeout=5

        )

        print("Status :", response.status_code)

    except Exception as e:

        print("送信失敗 :", e)


# ==========================================
# 初回画像取得
# ==========================================

previous_frame = picam2.capture_array()

print("初回画像取得")

# ==========================================
# 1分ごと監視
# ==========================================

INTERVAL = 60

try:

    while True:

        print("--------------------------------")
        print("1分待機中...")
        time.sleep(INTERVAL)

        print("撮影")

        current_frame = picam2.capture_array()

        if has_changed(previous_frame, current_frame):

            print("画像変化あり")

            rgb = cv2.cvtColor(
                current_frame,
                cv2.COLOR_BGRA2RGB
            )

            cv2.imwrite(
                "boardgame.jpg",
                cv2.cvtColor(
                    rgb,
                    cv2.COLOR_RGB2BGR
                )
            )

            print("Gemini推論中...")



            result = recognize_boardgame("boardgame.jpg")

            title = "何もしていない"

            for line in result.splitlines():
                if line.startswith("タイトル"):
                    title = line.split(":", 1)[1].strip()
                    break

            threading.Thread(
                target=send_to_server,
                args=(title,),
                daemon=True
            ).start()

            previous_frame = current_frame

        else:

            print("画像変化なし")

except KeyboardInterrupt:

    print("終了します")

finally:

    picam2.stop()

    print("camera stopped")