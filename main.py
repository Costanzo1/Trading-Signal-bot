from flask import Flask, request
import requests
import json
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def is_market_open():
    utc_now = datetime.now(timezone.utc)
    weekday = utc_now.weekday()
    hour = utc_now.hour
    month = utc_now.month
    day = utc_now.day
    
    if weekday >= 5 or (weekday == 4 and hour >= 21):
        return False
    
    holidays = [(1,1),(1,20),(2,17),(5,26),(6,19),(7,4),(9,1),(11,27),(12,25)]
    if (month, day) in holidays:
        return False
    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'UNKNOWN')
        price = data.get('price', 'N/A')
        
        if not is_market_open():
            return "Market closed", 200
        
        grok_resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "grok-3",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional and very selective swing trader specialized in daily and 4H timeframes.\nOnly give signals with minimum 78% confidence.\nIf no strong setup, respond ONLY with: {\"verdict\":\"NO\"}\nBase analysis on price action and market structure.\nRespond ONLY with valid JSON:\n{\"verdict\":\"BUY\" or \"SELL\" or \"NO\",\"probability\":number,\"entry\":number,\"sl\":number,\"tp1\":number,\"tp2\":number or null,\"reason\":\"short explanation\"}"
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
        
        if signal.get('verdict') == "NO" or signal.get('probability', 0) < 78:
            return "No strong signal", 200
        
        message = f"""🚨 **STRONG SIGNAL** — {signal.get('verdict')}
**Asset:** {symbol}
**Price:** {price}
**Entry:** {signal.get('entry')}
**SL:** {signal.get('sl')}
**TP1:** {signal.get('tp1')}
**TP2:** {signal.get('tp2') or '—'}
**Prob:** {signal.get('probability')}%
**Reason:** {signal.get('reason')}"""
        
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
        
        return "OK", 200
    except Exception as e:
        print("Error:", str(e))
        return "Error", 500

@app.route('/')
def home():
    return "Trading Signal Bot is running! ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
