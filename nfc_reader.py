import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import time

load_dotenv()

API_URL = os.getenv("API_URL")

last_read_time = 0
last_tag_id = None

COOLDOWN = 2  # 秒

# =========================
# サーバー送信
# =========================
def send_to_server(send_id):
    try:
        print("📡 送信:", send_id)

        res = requests.post(
            API_URL,
            json={
                "tag_id": send_id,
                "timestamp": datetime.now().isoformat()
            },
            timeout=1  # ← 短めで詰まり防止
        )

        print("✅ status:", res.status_code)

    except Exception as e:
        print("❌ 送信エラー:", e)


# =========================
# NFC検出
# =========================
def on_connect(tag):
    global last_read_time, last_tag_id

    print("🔵 on_connect 呼ばれた")

    now = time.time()

    # クールダウン
    if now - last_read_time < COOLDOWN:
        print("⏳ クールダウン中...")
        return True

    tag_id = tag.identifier.hex()
    print("🔍 検出:", tag_id)

    # トグル処理
    if tag_id == last_tag_id:
        send_id = "00"
        print("🔁 同じタグ → OFF")
        last_tag_id = None
    else:
        send_id = tag_id
        last_tag_id = tag_id

    # 👇 スレッド使わず同期で送信（安定）
    send_to_server(send_id)

    last_read_time = now

    return True


def on_release(tag):
    print("🔴 カード離れた")


# =========================
# メインループ
# =========================
def main():
    print("🚀 NFC起動中...")

    try:
        clf = nfc.ContactlessFrontend('usb:054c:06c3')
    except Exception as e:
        print("❌ NFC初期化エラー:", e)
        return

    while True:
        try:
            print("👀 NFC待機中...")

            clf.connect(
                rdwr={
                    'on-connect': on_connect,
                    'on-release': on_release
                }
            )

        except Exception as e:
            print("⚠️ NFCエラー:", e)
            time.sleep(1)


if __name__ == "__main__":
    main()