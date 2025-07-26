import oandapyV20
from oandapyV20.endpoints.instruments import InstrumentsCandles
from datetime import datetime, timedelta, timezone
from twilio.rest import Client
import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_TOKEN = os.getenv('OANDA_ACCESS_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
TO_WHATSAPP_NUMBER = os.getenv('TO_WHATSAPP_NUMBER')

client = oandapyV20.API(access_token=ACCESS_TOKEN)

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Send WhatsApp message ---
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

# --- CRT Signal Logic ---
def check_crt(c1, c2):
    l1 = float(c1['l'])  # Low of second last candle
    h1 = float(c1['h'])  # High of second last candle
    close1 = float(c1['c'])  # Close of second last candle

    l2 = float(c2['l'])  # Low of last candle
    h2 = float(c2['h'])  # High of last candle
    close2 = float(c2['c'])  # Close of last candle

    if l1 > l2 and close2 > l1:
        return "🟢 Bullish CRT"
    elif h1 < h2 and close2 < h1:
        return "🔴 Bearish CRT"
    return None

# --- Fetch 3 candles and evaluate signal ---
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

    c1 = candles[-3]['mid']  # second last closed
    c2 = candles[-2]['mid']  # last closed
    print(c1, c2)
    result = check_crt(c1, c2)
    print(result)
    if result:
        msg = f"[{granularity}] {result}"
        print(msg)
        send_whatsapp_message(msg)

# --- Main loop ---
def run_crt_bot():
    while True:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        minute = now.minute
        second = now.second
        day_of_week = now.weekday()  # 0=Monday, 6=Sunday
        hour = now.hour
        
        print(f"Day: {day_of_week}, Hour: {hour}, Minute: {minute}, Second: {second}")
        
        # Check if we're in the allowed time window
        in_time_window = False
        
        if day_of_week == 0:  # Monday
            if hour >= 3 or hour == 0:  # 3:30 AM onwards (including past midnight)
                in_time_window = True
        elif 1 <= day_of_week <= 3:  # Tuesday to Thursday
            in_time_window = True  # All day
        elif day_of_week == 4:  # Friday
            if hour <= 0 and minute <= 10:  # Until 12:10 AM
                in_time_window = True
            elif hour >= 3:  # From 3:30 AM onwards
                in_time_window = True
        
        # Only check at xx:30 and within time window
        if in_time_window and minute == 30 and 0 <= second <= 5:
            if now.hour % 1 == 0:
                print("🚀 Fetching H1 candles...")
                fetch_candles("H1")
            if now.hour % 4 == 0:
                print("🚀 Fetching H4 candles...")
                fetch_candles("H4")
        elif not in_time_window:
            print("⏸️ Outside trading hours - waiting...")
        
        time.sleep(1)

if __name__ == "__main__":
    print("🚀 CRT Bot started... Waiting for H1/H4 candle closes...")

    # Start bot loop
    run_crt_bot()
