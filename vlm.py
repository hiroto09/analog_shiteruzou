import os
import time
import requests
import cv2
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

from google import genai
from PIL import Image
from picamera2 import Picamera2

# =========================================================
# .env & 環境変数チェック
# =========================================================

load_dotenv()

# HOST_API_URL はホストサーバーの /analog エンドポイント
HOST_API_URL = os.getenv("API_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANALOG_EVENTS_API_URL = os.getenv("ANALOG_EVENTS_API_URL")

if not HOST_API_URL: raise ValueError("API_URL が設定されていません")
if not GEMINI_API_KEY: raise ValueError("GEMINI_API_KEY が設定されていません")
if not ANALOG_EVENTS_API_URL: raise ValueError("ANALOG_EVENTS_API_URL が設定されていません")

session = requests.Session()

# ログ設定
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "analog_prediction.log")
os.makedirs(LOG_DIR, exist_ok=True)


# =========================================================
# ゲーム一覧 & Prompt
# =========================================================

GAME_MAP = {"0": "何もしてない"}

def get_game_map():
    global GAME_MAP
    try:
        print("🎲 ゲーム一覧を取得しています...")
        response = session.get(ANALOG_EVENTS_API_URL, params={"game_type": "analog"}, timeout=10)
        response.raise_for_status()
        
        games = response.json()["data"]
        new_game_map = {"0": "何もしてない"}
        for game in games:
            new_game_map[str(game["ID"])] = game["Name"]
            
        GAME_MAP = new_game_map
        print("✅ ゲーム一覧取得完了")
    except Exception as e:
        print("❌ ゲーム一覧取得エラー:", e)

get_game_map()

client = genai.Client(api_key=GEMINI_API_KEY)
PROMPT_FILE = "prompt.txt"

if not os.path.exists(PROMPT_FILE):
    raise FileNotFoundError(f"{PROMPT_FILE} が見つかりません")

def create_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    candidates = "\n".join(f'    "{gid}": "{gname}",' for gid, gname in GAME_MAP.items())
    return prompt_template.replace("{GAME_CANDIDATES}", candidates)

PROMPT = create_prompt()


# =========================================================
# Camera & 推定設定
# =========================================================

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 640), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()
time.sleep(2)
print("📷 Camera started")

INTERVAL = 60
CHANGE_THRESHOLD = 200000
CONFIDENCE_THRESHOLD = 80


# =========================================================
# 推論・ヘルパー関数
# =========================================================

def has_changed(prev_frame, current_frame, threshold=CHANGE_THRESHOLD):
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_RGB2GRAY)
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_RGB2GRAY)
    diff = cv2.absdiff(prev_gray, curr_gray)
    _, diff = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
    return np.count_nonzero(diff) > threshold

def recognize_boardgame(image_path):
    image = Image.open(image_path)
    while True:
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=[image, PROMPT]
            )
            if response.text:
                return response.text
            raise RuntimeError("Geminiから応答がありません")
        except Exception as e:
            print("Geminiエラー:", e)
            if "503" in str(e) or "429" in str(e):
                time.sleep(300)
                continue
            time.sleep(300)

def parse_result(result):
    analog_id, confidence, reason = "0", 0, ""
    if not result: return analog_id, confidence, reason
    for line in result.splitlines():
        line = line.strip()
        if line.lower().startswith("id"):
            try: analog_id = line.split(":", 1)[1].strip()
            except: pass
        elif "信頼度" in line:
            try: confidence = int(line.split(":", 1)[1].replace("%", "").strip())
            except: pass
        elif "根拠" in line:
            try: reason = line.split(":", 1)[1].strip()
            except: pass
    return analog_id, confidence, reason

def write_prediction_log(result, analog_id, confidence, reason):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("========================================\n")
            f.write(f"日時: {timestamp}\nid: {analog_id}\n信頼度: {confidence}%\n根拠: {reason}\n")
            f.write("Gemini生回答:\n" + (result.strip() if result else "なし") + "\n")
            f.write("========================================\n\n")
    except Exception as e:
        print("ログ保存エラー:", e)

def notify_server(analog_id=None, inference_running=None):
    payload = {}
    if analog_id is not None:
        payload["analog_id"] = analog_id
    if inference_running is not None:
        payload["inference_running"] = inference_running

    try:
        session.post(HOST_API_URL, json=payload, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"❌ サーバーへの送信失敗: {e}")


# =========================================================
# メインループ
# =========================================================

def inference_loop():
    previous_frame = picam2.capture_array()
    print("🟢 監視開始")

    while True:
        try:
            time.sleep(INTERVAL)
            current_frame = picam2.capture_array()

            if not has_changed(previous_frame, current_frame):
                previous_frame = current_frame
                continue

            print("🔍 画面変化を検出、推論を開始します...")
            
            # ホストサーバーへ「推論中」を通知
            notify_server(inference_running=True)

            image_path = "boardgame.jpg"
            cv2.imwrite(image_path, current_frame)

            result = recognize_boardgame(image_path)
            analog_id, confidence, reason = parse_result(result)

            if confidence < CONFIDENCE_THRESHOLD:
                analog_id = "0"

            print(f"🎮 推定ID: {analog_id} (信頼度: {confidence}%)")
            write_prediction_log(result, analog_id, confidence, reason)

            # ホストサーバーへ「推論完了・結果」を通知
            notify_server(analog_id=analog_id, inference_running=False)

            previous_frame = current_frame

        except Exception as e:
            print("推定処理エラー:", e)
            notify_server(inference_running=False)

if __name__ == "__main__":
    try:
        inference_loop()
    except KeyboardInterrupt:
        print("\n⏹️ 終了処理中...")
        picam2.stop()
        print("Camera stopped")