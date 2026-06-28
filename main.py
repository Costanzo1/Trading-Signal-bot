from flask import Flask, request
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def is_market_open():
    now = datetime.utcnow()
    weekday = now.weekday()
    hour = now.hour
    month = now.month
    day = now.day

    if weekday >= 5:  # Weekend
        return False
    if weekday == 4 and hour >= 21:  # Friday after 21:00 UTC
        return False
    
    # US Holidays
    if (month == 1 and day == 1) or (month == 1 and day == 20) or \
       (month == 2 and day == 17) or (month == 5 and day == 26) or \
       (month == 6 and day == 19) or (month == 7 and day == 4) or \
       (month == 9 and day == 1) or (month == 11 and day == 27) or \
       (month == 12 and day == 25):
        return False
    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'UNKNOWN')
        price = data.get('price', 'N/A')
        
        if not is_market_open():
            print(f"Market closed - Ignored signal for {symbol}")
            return "Market closed", 200

        grok_resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-3",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert swing trader. Respond ONLY with valid JSON: {\"verdict\": \"BUY\" or \"SELL\" or \"NO\", \"probability\": number, \"entry\": number, \"sl\": number, \"tp1\": number, \"tp2\": number or null, \"reason\": \"short explanation\"}. Only strong setups >=70% probability."
                    },
                    {
                        "role": "user",
                        "content": f"Symbol: {symbol}\nCurrent Price: {price}"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 600
            }
        )
        
        result = grok_resp.json()
        content = result['choices'][0]['message']['content']
        signal = json.loads(content.strip())
        
        if signal.get('verdict') == "NO" or signal.get('probability', 0) < 70:
            return "No strong signal", 200

        message = f"""🚨 **STRONG SIGNAL** — {signal.get('verdict')}

**Asset:** {symbol}
**Current Price:** {price}

**Entry:** {signal.get('entry')}
**Stop Loss:** {signal.get('sl')}
**TP1:** {signal.get('tp1')}
**TP2:** {signal.get('tp2') or '—'}

**Probability:** {signal.get('probability')}%
**Reason:** {signal.get('reason')}"""

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
        
        print(f"Signal sent for {symbol}")
        return "OK", 200
        
    except Exception as e:
        print("Error:", str(e))
        return "Error", 500

@app.route('/')
def home():
    return "Trading Signal Bot is running! ✅"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
