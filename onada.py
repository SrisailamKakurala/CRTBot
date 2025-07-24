import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify
from dotenv import load_dotenv

import oandapyV20
from oandapyV20.endpoints.instruments import InstrumentsCandles
from twilio.rest import Client

# Load environment variables
load_dotenv()

# API Tokens and setup
ACCESS_TOKEN = os.getenv('OANDA_ACCESS_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
TO_WHATSAPP_NUMBER = os.getenv('TO_WHATSAPP_NUMBER')

client = oandapyV20.API(access_token=ACCESS_TOKEN)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Flask app
app = Flask(__name__)
bot_running = False  # Flag to show bot status

# --- WhatsApp Messaging ---
def send_whatsapp_message(body):
    try:
        twilio_client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=TO_WHATSAPP_NUMBER
        )
        print(f"📤 WhatsApp sent: {body}")
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")

# --- CRT Logic ---
def check_crt(c1, c2):
    l1, h1, close1 = float(c1['l']), float(c1['h']), float(c1['c'])
    l2, h2, close2 = float(c2['l']), float(c2['h']), float(c2['c'])

    if l1 > l2 and close2 > l1:
        return "🟢 Bullish CRT"
    elif h1 < h2 and close2 < h1:
        return "🔴 Bearish CRT"
    return None

def fetch_candles(granularity):
    params = {
        "granularity": granularity,
        "count": 3,
        "price": "M"
    }
    request = InstrumentsCandles(instrument="XAU_USD", params=params)
    client.request(request)
    candles = request.response['candles']

    if len(candles) < 3:
        print("⚠️ Not enough candle data.")
        return

    c1 = candles[-3]['mid']
    c2 = candles[-2]['mid']
    print(c1, c2)
    result = check_crt(c1, c2)
    print(result)
    if result:
        msg = f"[{granularity}] {result}"
        send_whatsapp_message(msg)

# --- Background CRT Bot ---
def run_crt_bot():
    global bot_running
    bot_running = True
    print("🚀 CRT Bot started... Waiting for H1/H4 candle closes...")

    while True:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        minute = now.minute
        second = now.second
        print(f"🕒 {minute}:{second}")

        if minute == 30 and 0 <= second <= 2:
            if now.hour % 1 == 0:
                print("🔍 Fetching H1 candles...")
                fetch_candles("H1")
            if now.hour % 4 == 0:
                print("🔍 Fetching H4 candles...")
                fetch_candles("H4")

        time.sleep(1)

# --- Flask Endpoints ---
@app.route("/")
def home():
    return jsonify({
        "status": "Bot is running" if bot_running else "Bot is not running"
    })

@app.route("/ping")
def ping():
    return "pong"

# --- Start everything ---
if __name__ == "__main__":
    # Start CRT bot in background
    threading.Thread(target=run_crt_bot, daemon=True).start()

    # Run Flask server
    app.run(debug=True, port=8000)
