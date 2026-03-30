import nfc
import requests
from datetime import datetime
import threading
import asyncio
import websockets
import json
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv

# --------------------
# .env 読み込み
# --------------------
load_dotenv()

API_URL = os.getenv("API_URL")
WS_URL = os.getenv("WS_URL")

last_tag_id = None
state_analog = "起動中..."

app = FastAPI()

# --------------------
# NFC送信
# --------------------
def on_connect(tag):
    global last_tag_id
    tag_id = tag.identifier.hex()

    send_id = "0" if tag_id == last_tag_id else tag_id
    last_tag_id = None if send_id == "0" else tag_id

    data = {
        "tag_id": send_id,
        "timestamp": datetime.now().isoformat()
    }

    try:
        res = requests.post(API_URL, json=data)
        print("送信成功:", res.json())
    except Exception as e:
        print("送信エラー:", e)

    return True

def nfc_loop():
    clf = nfc.ContactlessFrontend('usb')
    print("NFC待機中...")
    while True:
        clf.connect(rdwr={'on-connect': on_connect})

# --------------------
# WebSocket受信
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
        except Exception as e:
            print("WS切断、再接続:", e)
            await asyncio.sleep(1)

# --------------------
# HTML
# --------------------
@app.get("/")
def index():
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
body {{
  background: black;
  color: white;
  font-size: 140px;
  text-align: center;
  margin-top: 20%;
  font-family: sans-serif;
}}
</style>
</head>
<body>

<div id="analog">🃏 {state_analog}</div>

<script>
const ws = new WebSocket("{WS_URL}");

ws.onmessage = (event) => {{
  const data = JSON.parse(event.data);
  document.getElementById("analog").innerText = "🃏 " + data.analog;
}};

ws.onclose = () => {{
  setTimeout(() => location.reload(), 1000);
}};
</script>

</body>
</html>
""")

# --------------------
# 起動
# --------------------
def start():
    threading.Thread(target=nfc_loop, daemon=True).start()
    threading.Thread(target=lambda: asyncio.run(ws_loop()), daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    start()