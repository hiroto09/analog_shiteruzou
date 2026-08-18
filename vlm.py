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

if not API_URL:
    raise ValueError(
        "API_URL が設定されていません"
    )

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY が設定されていません"
    )


# ==========================================
# Prompt読み込み
# ==========================================

PROMPT_FILE = "prompt.txt"

if not os.path.exists(PROMPT_FILE):

    raise FileNotFoundError(
        f"{PROMPT_FILE} が見つかりません"
    )

ANALOG_EVENTS_API_URL = os.getenv("ANALOG_EVENTS_API_URL")


def get_analog_candidates():
    """
    StayWatch APIからanalogゲーム一覧を取得し、
    prompt.txtの候補欄に使用する文字列を作成する。
    """
    response = session.get(
        ANALOG_EVENTS_API_URL,
        params={"game_type": "analog"},
        timeout=10
    )

    response.raise_for_status()

    games = response.json()["data"]

    candidates = "\n".join(
        f'    "{game["ID"]:02d}": "{game["Name"]}",'
        for game in games
    )

    print("🎲 analogゲーム候補をAPIから取得しました")

    for game in games:
        print(
            f'    ID: {game["ID"]:02d}, '
            f'Name: {game["Name"]}'
        )

    return candidates


def create_prompt():
    """
    prompt.txtを読み込み、
    {GAME_CANDIDATES} をAPIから取得したanalog候補一覧に置き換える。
    """
    with open(
        PROMPT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        prompt_template = f.read()

    candidates = get_analog_candidates()

    return prompt_template.replace(
        "{GAME_CANDIDATES}",
        candidates
    )

# ==========================================
# ログ設定
# ==========================================

LOG_DIR = "logs"

LOG_FILE = os.path.join(
    LOG_DIR,
    "analog_prediction.log"
)

# logsディレクトリがなければ作成
os.makedirs(
    LOG_DIR,
    exist_ok=True
)

# ==========================================
# 推定結果ログ
# ==========================================

def write_prediction_log(
    result,
    analog_id,
    confidence,
    reason,
    sent_id
):

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    try:

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                "========================================\n"
            )

            f.write(
                f"日時: {timestamp}\n"
            )

            f.write(
                f"id: {analog_id}\n"
            )

            f.write(
                f"信頼度: {confidence}%\n"
            )

            f.write(
                f"根拠: {reason}\n"
            )

            f.write(
                f"送信ID: {sent_id}\n"
            )

            f.write(
                "Gemini生回答:\n"
            )

            if result:

                f.write(
                    result.strip()
                )

            else:

                f.write(
                    "Geminiから回答なし"
                )

            f.write(
                "\n"
            )

            f.write(
                "========================================\n\n"
            )


    except Exception as e:

        print(
            "⚠️ ログ保存エラー:"
        )

        print(e)


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


time.sleep(2)


# ==========================================
# 差分判定
# ==========================================

def has_changed(
    prev_frame,
    current_frame,
    threshold=200000
):

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

    changed_pixels = np.count_nonzero(
        diff
    )

    return changed_pixels > threshold


# ==========================================
# Gemini 推論
# ==========================================

def recognize_boardgame(
    image_path
):

    image = Image.open(
        image_path
    )

    while True:

        try:


            # 推論ごとにAPIから最新のanalogゲーム一覧を取得
            prompt = create_prompt()

            response = client.models.generate_content(

                model="gemini-flash-latest",

                contents=[
                    image,
                    prompt
                ]

            )

            if response.text:

                return response.text

            raise RuntimeError(
                "Geminiから応答がありません"
            )


        except Exception as e:

            print(
                "Geminiエラー"
            )

            print(e)

            error = str(e)


            # ==================================
            # 503
            # ==================================

            if "503" in error:

                print(
                    "503エラーのため60秒待機"
                )

                time.sleep(300)

                continue


            # ==================================
            # 429
            # ==================================

            if "429" in error:

                print(
                    "⚠️ Gemini APIのクォータ超過"
                )

                print(
                    "60秒後に再試行します"
                )

                time.sleep(300)

                continue


            # ==================================
            # その他
            # ==================================

            print(
                "⚠️ Geminiエラー"
            )

            print(
                "60秒後に再試行します"
            )

            time.sleep(300)


# ==========================================
# API送信
# ==========================================

def send_to_server(
    analog_id
):

    try:


        response = session.post(

            API_URL,

            json={
                "analog_id": analog_id,
                "timestamp": datetime.now().isoformat()
            },

            timeout=5

        )

        print(
            "Status :",
            response.status_code
        )

        print(
            "Response :",
            response.text
        )

    except Exception as e:

        print(
            "❌ 送信失敗 :",
            e
        )


# ==========================================
# Gemini結果解析
# ==========================================

def parse_result(
    result
):

    analog_id = "0"

    confidence = 0

    reason = ""


    if not result:

        return (
            analog_id,
            confidence,
            reason
        )


    for line in result.splitlines():

        line = line.strip()


        # ==================================
        # ID
        # ==================================

        if line.lower().startswith(
            "id"
        ):

            try:

                analog_id = line.split(
                    ":",
                    1
                )[1].strip()

            except (
                IndexError,
                ValueError
            ):

                analog_id = "0"


        # ==================================
        # 信頼度
        # ==================================

        elif "信頼度" in line:

            try:

                confidence = int(

                    line.split(
                        ":",
                        1
                    )[1]
                    .replace(
                        "%",
                        ""
                    )
                    .strip()

                )

            except (
                IndexError,
                ValueError
            ):

                confidence = 0


        # ==================================
        # 根拠
        # ==================================

        elif "根拠" in line:

            try:

                reason = line.split(
                    ":",
                    1
                )[1].strip()

            except (
                IndexError,
                ValueError
            ):

                reason = ""


    return (
        analog_id,
        confidence,
        reason
    )


# ==========================================
# 初回画像取得
# ==========================================

previous_frame = picam2.capture_array()

print(
    "初回画像取得"
)


# ==========================================
# 監視間隔
# ==========================================

INTERVAL = 60


# ==========================================
# メインループ
# ==========================================

try:

    while True:

        print(
            "--------------------------------"
        )

        time.sleep(
            INTERVAL
        )

        current_frame = (
            picam2.capture_array()
        )

        # ==================================
        # プレビュー
        # ==================================

        cv2.imshow(
            "Preview",
            current_frame
        )

        cv2.waitKey(1)


        # ==================================
        # 差分チェック
        # ==================================

        if has_changed(

            previous_frame,

            current_frame

        ):


            # ==================================
            # 画像保存
            # ==================================

            cv2.imwrite(
                "boardgame.jpg",
                current_frame
            )


            # ==================================
            # Gemini推論
            # ==================================

            result = recognize_boardgame(

                "boardgame.jpg"

            )


            # ==================================
            # Gemini結果表示
            # ==================================


            # ==================================
            # 結果解析
            # ==================================

            (
                analog_id,
                confidence,
                reason
            ) = parse_result(
                result
            )


            # ==================================
            # 信頼度チェック
            # ==================================

            if confidence < 80:


                analog_id = "0"


            # ==================================
            # 最終結果
            # ==================================

            print(
                f"🎮 推定ID : {analog_id}"
            )

            print(
                f"📊 信頼度 : {confidence}%"
            )


            # ==================================
            # API送信用ID
            # ==================================

            sent_id = analog_id


            # ==================================
            # ログ保存
            # ==================================

            write_prediction_log(

                result=result,

                analog_id=analog_id,

                confidence=confidence,

                reason=reason,

                sent_id=sent_id

            )


            # ==================================
            # API送信
            # ==================================

            threading.Thread(

                target=send_to_server,

                args=(sent_id,),

                daemon=True

            ).start()


            # ==================================
            # 前回画像更新
            # ==================================

            previous_frame = (
                current_frame
            )


        else:

            print(
                "変化なし"
            )


except KeyboardInterrupt:

    print(
        "終了します"
    )


finally:

    picam2.stop()

    cv2.destroyAllWindows()

    print(
        "camera stopped"
    )
