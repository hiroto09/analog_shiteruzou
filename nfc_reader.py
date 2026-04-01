import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import time

load_dotenv()

API_URL = os.getenv("API_URL")

last_tag_id = None
is_on = False  # ← 状態追加
last_read_time = 0

COOLDOWN = 2

def on_connect(tag):
    global last_tag_id, is_on, last_read_time

    now = time.time()

    if now - last_read_time < COOLDOWN:
        print("⏳ クールダウン中...")
        return True

    tag_id = tag.identifier.hex()
    print("検出:", tag_id)

    # 🎯 トグル処理
    if not is_on:
        send_id = tag_id
        print("→ ON")
        is_on = True
        last_tag_id = tag_id
    else:
        send_id = "0"
        print("→ OFF")
        is_on = False
        last_tag_id = None  # ← リセット重要

    # サーバー送信
    requests.post(API_URL, json={
        "tag_id": send_id,
        "timestamp": datetime.now().isoformat()
    })

    last_read_time = now

    return True


def on_release(tag):
    print("カード離れた")
    pass


clf = nfc.ContactlessFrontend('usb:054c:06c3')  # ← これも忘れずに

print("NFC待機中...")

clf.connect(rdwr={
    'on-connect': on_connect,
    'on-release': on_release
})