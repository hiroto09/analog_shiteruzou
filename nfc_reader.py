import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import time
import threading

load_dotenv()

API_URL = os.getenv("API_URL")
last_read_time = 0

COOLDOWN = 2

def send_to_server(send_id):
    try:
        requests.post(API_URL, json={
            "tag_id": send_id,
            "timestamp": datetime.now().isoformat()
        }, timeout=2)
    except Exception as e:
        print("送信エラー:", e)

def on_connect(tag):
    global last_read_time

    now = time.time()

    if now - last_read_time < COOLDOWN:
        print("⏳ クールダウン中...")
        return True

    tag_id = tag.identifier.hex()
    print("検出:", tag_id)

    # 常にタグID送信
    threading.Thread(target=send_to_server, args=(tag_id,)).start()
    last_read_time = now

    return True


def on_release(tag):
    print("カード離れた")

clf = nfc.ContactlessFrontend('usb:054c:06c3')

print("NFC待機中...")


while True:
    try:
        clf.connect(rdwr={
            'on-connect': on_connect,
            'on-release': on_release
        })
    except Exception as e:
        print("NFCエラー:", e)
        time.sleep(1)