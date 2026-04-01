import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import time

load_dotenv()

API_URL = os.getenv("API_URL")

last_tag_id = None
last_read_time = 0   # ← 追加

COOLDOWN = 2  # 秒

def on_connect(tag):
    global last_tag_id, last_read_time

    now = time.time()

    # 🔒 クールダウン中なら無視
    if now - last_read_time < COOLDOWN:
        print("⏳ クールダウン中...")
        return True

    tag_id = tag.identifier.hex()
    print("検出:", tag_id)

    # トグル判定
    if tag_id == last_tag_id:
        send_id = "0"
        print("→ 同じカードなのでOFF")
        last_tag_id = None
    else:
        send_id = tag_id
        print("→ 新しいカードなのでON")
        last_tag_id = tag_id

    # サーバー送信
    requests.post(API_URL, json={
        "tag_id": send_id,
        "timestamp": datetime.now().isoformat()
    })

    # ⏱ 最終読み取り時間を更新
    last_read_time = now

    return True


def on_release(tag):
    print("カード離れた")
    pass


clf = nfc.ContactlessFrontend('usb')

print("NFC待機中...")

clf.connect(rdwr={
    'on-connect': on_connect,
    'on-release': on_release
})