# nfc_ws_client.py
import nfc
import requests
from datetime import datetime
import threading
import asyncio
import websockets
import json

API_URL = "http://<ホストサーバーIP>:8000/analog"
WS_URL = "ws://<ホストサーバーIP>:8000/ws"

last_tag_id = None
state_analog = "起動中..."

# --------------------
# NFC送信
# --------------------
def on_connect(tag):
    global last_tag_id
    tag_id = tag.identifier.hex()

    send_id = "0" if tag_id == last_tag_id else tag_id
    last_tag_id = None if send_id == "0" else tag_id

    data = {"tag_id": send_id, "timestamp": datetime.now().isoformat()}

    try:
        res = requests.post(API_URL, json=data)
        print("送信成功:", res.json())
    except Exception as e:
        print("送信エラー:", e)

    return True

def nfc_loop():
    clf = nfc.ContactlessFrontend('usb')
    while True:
        clf.connect(rdwr={'on-connect': on_connect})

# --------------------
# WebSocketで受信してHTMLに反映
# --------------------
async def ws_loop():
    global state_analog
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                async for message in ws:
                    data = json.loads(message)
                    state_analog = data.get("analog", "不明")
                    print("最新analog:", state_analog)
                    update_html(state_analog)
        except Exception as e:
            print("WS切断、再接続します:", e)
            await asyncio.sleep(1)

# --------------------
# HTML更新
# --------------------
def update_html(analog):
    with open("/var/www/html/index.html", "w", encoding="utf-8") as f:
        f.write(f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{ background: black; color: white; font-size: 140px; text-align: center; margin-top: 20%; font-family: sans-serif; }}
</style>
</head>
<body>
<div id="analog">🃏 {analog}</div>
</body>
</html>
""")

# --------------------
# スレッドとメイン
# --------------------
threading.Thread(target=nfc_loop, daemon=True).start()

# 初回HTML書き込み
update_html(state_analog)

# WebSocketループ
asyncio.run(ws_loop())