import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

API_URL = os.getenv("API_URL")

if not API_URL:
    raise ValueError("API_URLが.envに設定されていません")

last_tag_id = None

def on_connect(tag):
    global last_tag_id

    tag_id = tag.identifier.hex()
    print("検出:", tag_id)

    if tag_id == last_tag_id:
        send_id = "0"
        last_tag_id = None
        print("→ OFF")
    else:
        send_id = tag_id
        last_tag_id = tag_id
        print("→ ON")

    requests.post(API_URL, json={
        "tag_id": send_id,
        "timestamp": datetime.now().isoformat()
    })

    return True

clf = nfc.ContactlessFrontend('usb')

print("NFC待機中...")
clf.connect(rdwr={'on-connect': on_connect})