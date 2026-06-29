from flask import Flask, request
import requests
import json
import os
import re
from datetime import datetime
from threading import Thread

app = Flask(__name__)

GROK_API_KEY = os.getenv("GROK_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def is_market_open():
    """Check if forex/major markets are likely open (UTC)."""
    now = datetime.utcnow()
    if now.weekday() == 5:  # Saturday
        return False
    if now.weekday() == 6 and now.hour < 22:  # Sunday before 22:00 UTC
        return False
    if now.weekday() == 4 and now.hour >= 22:  # Friday after 22:00 UTC
        return False
    return True

def send_telegram(message):
    """Send message to Telegram with error handling."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"Telegram Error: {e}")

def analyze_with_grok(symbol, price):
    """Analyze signal with Grok API and send to Telegram if strong."""
    try:
        grok_resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-beta",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a professional selective swing trader. "
                            "Only give high quality setups with minimum 78% confidence. "
                            "If no strong setup respond ONLY with {\"verdict\":\"NO\"}. "
                            "Keep reason very short. "
                            "Respond ONLY with this exact JSON format: "
                            "{\"verdict\":\"BUY\" or \"SELL\" or \"NO\","
                            "\"probability\":number,"
                            "\"entry\":number,"
                            "\"sl\":number,"
                            "\"tp1\":number,"
                            "\"tp2\":null,"
                            "\"reason\":\"short explanation\"}"
                        )
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
        grok_resp.raise_for_status()
        
        result = grok_resp.json()
        content = result['choices'][0]['message']['content']
        
        # Extract JSON from response (Grok might wrap it in markdown)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            print(f"No JSON found in Grok response: {content[:200]}")
            return
            
        signal = json.loads(json_match.group())
        
        verdict = signal.get('verdict', 'NO')
        probability = signal.get('probability', 0)
        
        if verdict == "NO" or probability < 78:
            print(f"Signal rejected: verdict={verdict}, probability={probability}")
            return

        message = (
            f"🚨 *STRONG SIGNAL — {verdict} {symbol}*\n\n"
            f"💰 Price: `{price}`\n"
            f"🎯 Entry: `{signal.get('entry')}`\n"
            f"🛑 SL: `{signal.get('sl')}`\n"
            f"✅ TP1: `{signal.get('tp1')}`\n"
            f"✅ TP2: `{signal.get('tp2') or '—'}`\n"
            f"📊 Probability: `{probability}%`\n"
            f"📝 Reason: _{signal.get('reason', 'N/A')}_"
        )

        send_telegram(message)

    except requests.exceptions.RequestException as e:
        print(f"Grok API Error: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
    except Exception as e:
        print(f"Grok Analysis Error: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive TradingView webhook and process asynchronously."""
    try:
        if not request.is_json:
            return "Content-Type must be application/json", 400

        data = request.get_json()
        
        symbol = data.get('symbol')
        price = data.get('price')
        
        if not symbol or price is None:
            return "Missing required fields: symbol, price", 400

        try:
            price = float(price)
        except (ValueError, TypeError):
            return "Invalid price format", 400

        if not is_market_open():
            print(f"Market closed - ignoring signal for {symbol}")
            return "Market closed", 200

        thread = Thread(target=analyze_with_grok, args=(symbol, price), daemon=True)
        thread.start()

        return "OK", 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return "Internal Server Error", 500

@app.route('/')
def home():
    return "Trading Signal Bot (Async) is running! ✅"

@app.route('/health')
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}, 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
