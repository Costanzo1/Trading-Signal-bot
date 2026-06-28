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

@app.route('/webhook', methods= )
def webhook():
    try:
        data = request.json
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
                        "content": "You are an expert swing trader. Analyze the current price and give a clear trading signal. Respond ONLY with valid JSON in this exact format: {\"verdict\":\"BUY\",\"probability\":85,\"entry\":2650.5,\"sl\":2635,\"tp1\":2670,\"tp2\":2685,\"reason\":\"strong support level\"} or {\"verdict\":\"NO\"} if no good setup."
                    },
                    {
                        "role": "user",
                        "content": f"Symbol: {symbol}\nCurrent Price: {price}\nGive me your best trading analysis."
                    }
                ],
                "temperature": 0.3
            }
        )
        
        result = grok_resp.json()
        content = result [0]  signal = json.loads(content.strip())
        
        if signal.get('verdict') == "NO":
            return "No signal", 200

        message = f"""🚨 **NEW SIGNAL** - {signal.get('verdict')}

**Asset:** {symbol}
**Price:** {price}

**Entry:** {signal.get('entry')}
**Stop Loss:** {signal.get('sl')}
**TP1:** {signal.get('tp1')}
**TP2:** {signal.get('tp2')}

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
