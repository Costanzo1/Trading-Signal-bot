from flask import Flask, request
import requests
import json
import os
from datetime import datetime
from threading import Thread

app = Flask(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def is_market_open():
    now = datetime.utcnow()
    if now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 21):
        return False
    return True

def analyze_with_grok(symbol, price):
    try:
        grok_resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "grok-beta",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional selective swing trader. Only give high quality setups with minimum 78% confidence. If no strong setup respond ONLY with {\"verdict\":\"NO\"}. Keep reason very short. Respond ONLY with this exact JSON format: {\"verdict\":\"BUY\" or \"SELL\" or \"NO\",\"probability\":number,\"entry\":number,\"sl\":number,\"tp1\":number,\"tp2\":null,\"reason\":\"short explanation\"}"
                    },
                    {
                        "role": "user",
                        "content": f"Symbol: {symbol}\nCurrent Price: {price}"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 350
            },
            timeout=15
        )

        result = grok_resp.json()
        content = result['choices'][0]['message']['content']
        signal = json.loads(content.strip())

        if signal.get('verdict') == "NO" or signal.get('probability', 0) < 78:
            return

        message = f"""🚨 STRONG SIGNAL — {signal.get('verdict')} {symbol}

Price: {price}
Entry: {signal.get('entry')}
SL: {signal.get('sl')}
TP1: {signal.get('tp1')}
TP2: {signal.get('tp2') or '—'}
Probability: {signal.get('probability')}%
Reason: {signal.get('reason')}"""

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": message})

    except Exception as e:
        print("Grok Error:", str(e))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'UNKNOWN')
        price = data.get('price', 'N/A')

        if not is_market_open():
            return "Market closed", 200

        # Avvia analisi in background
        Thread(target=analyze_with_grok, args=(symbol, price)).start()

        return "OK", 200

    except Exception as e:
        print("Webhook Error:", str(e))
        return "Error", 500

@app.route('/')
def home():
    return "Trading Signal Bot (Async) is running! ✅"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
