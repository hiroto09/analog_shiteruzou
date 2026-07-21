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
    main={
        "size": (640, 640),
        "format": "RGB888"
    }
)

picam2.configure(config)
picam2.start()

print("camera started")

time.sleep(2)

# ==========================================
# 差分判定
# ==========================================

def has_changed(prev_frame, current_frame, threshold=150000):

    prev_gray = cv2.cvtColor(
    prev_frame,
    cv2.COLOR_RGB2GRAY
    )

    curr_gray = cv2.cvtColor(
        current_frame,
        cv2.COLOR_RGB2GRAY
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

    while True:

        try:

            response = client.models.generate_content(

                model="gemini-2.5-flash-lite",

                contents=[
                    image,
                    """
    画像に写っているボードゲームを推定してください。

    以下の候補から最も近いものを1つ選んでください。

    候補
    "00": "ボードゲームをしていない",
    "01": "カタカナーシ", 
    "02": "チェス", 
    "03": "モダンアート", 
    "04": "マーダーミステリー", 
    "05": "UIかるた",
    "06": "カラーコードかるた", 
    "07": "Linuxコマンドかるた", 
    "08": "トランプ", 
    "09": "お邪魔者", 
    "10": "カタン(大航海時代)", 
    "11": "キャンプ場の殺人鬼", 
    "12": "コヨーテ", 
    "13": "犯人は踊る", 
    "14": "犯人は踊る3", 
    "15": "お邪魔者2", 
    "16": "トランプ", 
    "17": "ファットプロジェクト", 
    "18": "プログラム言語神経衰弱", 
    "19": "テストプレイなんてしてないよ", 
    "20": "まじかる★ベーカリー", 
    "21": "カタン(スタンダート)", 
    "22": "カタン(スタンダート)", 
    "23": "ito", 
    "24": "人狼", 
    "25": "プロポーズ", 
    "26": "麻雀",
    "27": "宝石の煌めき"

    この画像の机には，ボードゲームを行なっていない状態(作業や食事，パソコンやスマホなどの物置)として利用されている場合があります．
    また緑のマットが机の上に常に敷かれているが，その上にボードゲームが置かれていない場合もあります．
    そういった場合や推定結果に明確な根拠がない場合は 00 を返してください。

    回答は次の形式のみで出力してください。
    id: 〇〇
    信頼度: 〇〇%
"""
                ]
            )

            return response.text

        except Exception as e:

            print("Geminiエラー")
            print(e)

            # 503なら30秒待って再試行
            if "503" in str(e):
                print("Geminiサーバーが混雑しています。30秒後に再試行します。")
                time.sleep(30)
                continue

            # その他のエラーも10秒後に再試行
            print("10秒後に再試行します。")
            time.sleep(10)


# ==========================================
# API送信
# ==========================================

def send_to_server(analog_id):

    try:

        print("送信開始")

        response = session.post(

            API_URL,

            json={
                "analog_id": analog_id,
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
        

        cv2.imshow(
            "Preview",
            current_frame
        )

        cv2.waitKey(1)

        if has_changed(previous_frame, current_frame):

            print("画像変化あり")

            cv2.imwrite(
                "boardgame.jpg",
                current_frame
            )

            print("Gemini推論中...")



            result = recognize_boardgame("boardgame.jpg")

            analog_id = "00"

            for line in result.splitlines():

                if line.lower().startswith("id"):

                    analog_id = line.split(":", 1)[1].strip().replace('"', "")

                    break

            print("Gemini結果")
            print(result)
            print("送信ID :", analog_id)

            threading.Thread(
                target=send_to_server,
                args=(analog_id,),
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