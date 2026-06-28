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

    # Weekend
    if weekday >= 5:
        return False
    
    # Friday after 21:00 UTC
    if weekday == 4 and hour >= 21:
        return False

    # US Market Holidays (principali)
    if (month == 1 and day == 1) or \
       (month == 1 and day == 20) or \
       (month == 2 and day == 17) or \
       (month == 5 and day == 26) or \
       (month == 6 and day == 19) or \
       (month == 7 and day == 4) or \
       (month == 9 and day == 1) or \
       (month == 11 and day == 27) or \
       (month == 12 and day == 25):
        return False

    return True

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        symbol = data.get('symbol', 'XAUUSD')
        price = data.get('price', 'N/A')
        
        if not is_market_open():
            print("Market closed or holiday - No signal sent")
            return "Market closed", 200
        
        # Chiamata a Grok
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
                        "content": "You are an expert swing trader specialized in daily and weekly timeframes. Always respond ONLY with valid JSON using this exact format and nothing else: {\"verdict\":\"BUY\" or \"SELL\" or \"NO\",\"probability\":number,\"entry\":number,\"sl\":number,\"tp1\":number,\"tp2\":number,\"reason\":\"short explanation\"}."
                    },
                    {
                        "role": "user",
                        "content": f"Symbol: {symbol}\nCurrent Price: {price}\nGive me a strong trading signal."
                    }
                ],
                "temperature": 0.3
            }
        )
        
        result = grok_resp.json()
        content = result['choices'][0]['message']['content']
        signal = json.loads(content.strip())
        
        message = f"""🚨 **NEW SIGNAL** - {signal.get('verdict', 'NO')}

**Asset:** {symbol}
**Current Price:** {price}
**Entry:** {signal.get('entry', 'N/A')}
**Stop Loss:** {signal.get('sl', 'N/A')}
**TP1:** {signal.get('tp1', 'N/A')}
**TP2:** {signal.get('tp2', 'N/A')}

**Probability:** {signal.get('probability', 'N/A')}%
**Reason:** {signal.get('reason', 'N/A')}"""

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})
        
        print("✅ Segnale inviato su Telegram")
        return "OK", 200
        
    except Exception as e:
        print("❌ Errore:", str(e))
        return "Error", 500

@app.route('/')
def home():
    return "Trading Signal Bot is running! ✅"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
