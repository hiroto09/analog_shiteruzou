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

# フォールバック用モデルリスト（優先順位順）
FALLBACK_MODELS = [
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]


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
    
    # 変化したピクセル数と全ピクセル数を計算
    changed_pixels = np.count_nonzero(diff)
    total_pixels = diff.size
    percentage = (changed_pixels / total_pixels) * 100
    
    print(f"📊 画面変化: {changed_pixels:,} / {total_pixels:,} px ({percentage:.2f}%) - 閾値: {threshold:,} px")
    
    return changed_pixels > threshold

def recognize_boardgame(image_path):
    """
    Gemini APIを呼び出し、503エラー時には次のモデルへフォールバックして再試行する
    """
    image = Image.open(image_path)
    
    while True:
        for model_name in FALLBACK_MODELS:
            try:
                print(f"🤖 Gemini 推論中 (モデル: {model_name})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[image, PROMPT]
                )
                if response.text:
                    print(f"✅ Gemini 応答受信用 (モデル: {model_name})")
                    return response.text
                
                raise RuntimeError(f"Gemini({model_name})から応答本文がありません")

            except Exception as e:
                err_msg = str(e)
                print(f"❌ Geminiエラー ({model_name}): {err_msg}")

                # 503 (Service Unavailable / 高負荷) の場合は次のモデルで即時再試行
                if "503" in err_msg:
                    print(f"🔄 503エラーを検知。別のモデルに切り替えます...")
                    time.sleep(2)  # 連続アクセス負荷軽減のための微少ウェイト
                    continue

                # 429 (Too Many Requests / レート制限) の場合はモデルを変えても解決しないため1時間待機
                if "429" in err_msg:
                    print("⚠️ 429エラー(レート制限)が発生。1時間待機します...")
                    time.sleep(3600)
                    break  # ループを抜けて最初(第1候補)からやり直し

                # その他の未知のエラーの場合
                print("⚠️ 10分待機後に再試行します...")
                time.sleep(600)
                break

        else:
            # FALLBACK_MODELS 内の全モデルで503エラーなどが起き、breakされずに一巡した場合
            print("⚠️ すべてのモデルで失敗しました。5分待機後に最初のモデルから再試行します...")
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

def notify_server(analog_id=None, inference_running=None, image_path=None):
    """
    ホストサーバーへステータスや推論結果・画像を送信する関数
    画像が指定されている場合は multipart/form-data でファイル添付送信
    """
    data = {}
    if analog_id is not None:
        data["analog_id"] = str(analog_id)
    if inference_running is not None:
        data["inference_running"] = str(inference_running)

    files = None
    file_obj = None

    try:
        if image_path and os.path.exists(image_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analog_{analog_id or 'unknown'}_{timestamp}.jpg"
            file_obj = open(image_path, "rb")
            files = {"image": (filename, file_obj, "image/jpeg")}

        # files がある場合は multipart/form-data (data=) で送信、無ければ JSON (json=) で送信
        if files:
            res = session.post(HOST_API_URL, data=data, files=files, timeout=10)
        else:
            res = session.post(HOST_API_URL, json=data, timeout=5)
            
        res.raise_for_status()
        print(f"📤 サーバー通知完了 (HTTP Status: {res.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ サーバーへの送信失敗: {e}")
    finally:
        if file_obj:
            file_obj.close()


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
            
            # ホストサーバーへ「推論中」を通知
            notify_server(inference_running=True)

            image_path = "boardgame.jpg"
            # opencvのimwriteを使う場合、RGBをBGRに変換する必要があるため修正
            cv2.imwrite(image_path, cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR))

            result = recognize_boardgame(image_path)
            analog_id, confidence, reason = parse_result(result)

            if confidence < CONFIDENCE_THRESHOLD:
                analog_id = "0"

            print(f"🎮 推定ID: {analog_id} (信頼度: {confidence}%)")
            write_prediction_log(result, analog_id, confidence, reason)

            # ホストサーバーへ「推論完了・結果・撮影画像」を通知
            notify_server(analog_id=analog_id, inference_running=False, image_path=image_path)

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