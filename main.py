import nfc
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
import threading

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

load_dotenv()

api_url = os.getenv("API_URL")

# =========================
# 状態保存（Web表示用）
# =========================
latest_status = "未検出"
latest_time = "-"

# =========================
# NFC側
# =========================
last_tag_id = None

def on_connect(tag):
    global last_tag_id, latest_status, latest_time

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
        res_json = res.json()

        print("送信成功:", res_json)

        # 👇 ここでレスポンスを保存（重要）
        latest_status = res_json.get("analog_status", "不明")
        latest_time = res_json.get("time", "-")

    except Exception as e:
        print("送信エラー:", e)

    return True


def nfc_loop():
    clf = nfc.ContactlessFrontend('usb')

    print("タッチしてください...")

    while True:
        clf.connect(rdwr={'on-connect': on_connect})


# =========================
# FastAPI（Web表示）
# =========================
app = FastAPI()

@app.get("/status")
def status():
    return {
        "analog_status": latest_status,
        "time": latest_time
    }

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
    <body style="font-family:sans-serif;">
        <h1>🎲 アナログ状態</h1>
        <p id="status"></p>
        <p id="time"></p>

        <script>
        async function update() {
            const res = await fetch('/status');
            const data = await res.json();

            document.getElementById('status').innerText =
                "🎲 " + data.analog_status;

            document.getElementById('time').innerText =
                "⏰ " + data.time;
        }

        setInterval(update, 1000);
        update();
        </script>
    </body>
    </html>
    """


# =========================
# 同時起動
# =========================
if __name__ == "__main__":
    # NFCを別スレッドで起動
    threading.Thread(target=nfc_loop, daemon=True).start()

    # Webサーバー起動
    uvicorn.run(app, host="0.0.0.0", port=8000)