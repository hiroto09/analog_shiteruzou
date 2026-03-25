import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

api_url = os.getenv("API_URL")

last_tag_id = None

def on_connect(tag):
    global last_tag_id

    print("カード検出！")

    tag_id = tag.identifier.hex()
    print("ID:", tag_id)

    # トグル
    if tag_id == last_tag_id:
        send_id = "0"
        last_tag_id = None
        print("→ OFF")
    else:
        send_id = tag_id
        last_tag_id = tag_id
        print("→ ON")

    data = {
        "tag_id": send_id,
        "confidence": 1.0,
        "timestamp": datetime.now().isoformat()
    }

    try:
        res = requests.post(api_url, json=data)
        print("送信成功:", res.json())
    except Exception as e:
        print("送信エラー:", e)

    return True


clf = nfc.ContactlessFrontend('usb')

print("タッチしてください...")

# 👇 ここが重要（無限ループ）
while True:
    clf.connect(rdwr={'on-connect': on_connect})