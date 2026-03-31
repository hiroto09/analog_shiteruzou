// nfc.js
require('dotenv').config();

const { NFC } = require('nfc-pcsc');
const fetch = global.fetch || require('node-fetch');

const API_URL = process.env.API_URL;

const nfc = new NFC();

let lastTagId = null;
let lastScanTime = 0;

console.log("NFC待機中...");

nfc.on('reader', reader => {

    reader.on('card', async card => {
        const now = Date.now();

        // 🔥 連打防止（2秒以内無視）
        if (now - lastScanTime < 2000) {
            return;
        }
        lastScanTime = now;

        const tagId = card.uid;
        console.log("検出:", tagId);

        let sendId;

        // 🔁 トグル
        if (tagId === lastTagId) {
            sendId = "0";
            lastTagId = null;
            console.log("→ OFF");
        } else {
            sendId = tagId;
            lastTagId = tagId;
            console.log("→ ON");
        }

        try {
            await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tag_id: sendId,
                    timestamp: new Date().toISOString()
                })
            });
        } catch (e) {
            console.error("送信エラー:", e);
        }
    });
});