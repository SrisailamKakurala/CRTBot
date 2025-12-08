import oandapyV20
from oandapyV20.endpoints.instruments import InstrumentsCandles
from datetime import datetime, timedelta, timezone
from twilio.rest import Client
import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import sys

load_dotenv()

ACCESS_TOKEN = os.getenv('OANDA_ACCESS_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
TO_WHATSAPP_NUMBER = os.getenv('TO_WHATSAPP_NUMBER')

# Testing mode configuration
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true' or '--test' in sys.argv
FORCE_CRT_SIGNAL = os.getenv('FORCE_CRT_SIGNAL', 'none').lower()  # 'bullish', 'bearish', 'none'
TEST_WHATSAPP = '--testw' in sys.argv

if TEST_MODE:
    print("⚠️ TEST MODE ENABLED ⚠️")
    if FORCE_CRT_SIGNAL != 'none':
        print(f"🧪 Forcing {FORCE_CRT_SIGNAL.upper()} CRT signals")

if TEST_WHATSAPP:
    print("📱 WHATSAPP TEST MODE ENABLED 📱")

client = oandapyV20.API(access_token=ACCESS_TOKEN, environment="practice")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Send WhatsApp message ---
def send_whatsapp_message(body):
    try:
        twilio_client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=TO_WHATSAPP_NUMBER
        )
        if TEST_MODE or TEST_WHATSAPP:
            print(f"🧪 [TEST] WhatsApp sent: {body}")
        else:
            print(f"📤 WhatsApp sent: {body}")
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")

# --- Test WhatsApp with mock data ---
def test_whatsapp_messages():
    print("\n" + "="*60)
    print("🧪 TESTING WHATSAPP MESSAGING WITH MOCK DATA")
    print("="*60 + "\n")
    
    mock_signals = [
        {
            "granularity": "H1",
            "signal": "🟢 Bullish CRT",
            "c1": {'o': '4217.190', 'h': '4217.610', 'l': '4206.310', 'c': '4206.830'},
            "c2": {'o': '4206.815', 'h': '4216.695', 'l': '4203.175', 'c': '4209.875'}
        },
        {
            "granularity": "H1",
            "signal": "🔴 Bearish CRT",
            "c1": {'o': '4210.500', 'h': '4220.300', 'l': '4208.100', 'c': '4215.800'},
            "c2": {'o': '4215.900', 'h': '4225.500', 'l': '4210.200', 'c': '4212.400'}
        },
        {
            "granularity": "H4",
            "signal": "🟢 Bullish CRT",
            "c1": {'o': '4200.000', 'h': '4210.000', 'l': '4190.000', 'c': '4195.000'},
            "c2": {'o': '4195.500', 'h': '4205.000', 'l': '4185.000', 'c': '4202.000'}
        },
        {
            "granularity": "H4",
            "signal": "🔴 Bearish CRT",
            "c1": {'o': '4220.000', 'h': '4230.000', 'l': '4215.000', 'c': '4225.000'},
            "c2": {'o': '4225.500', 'h': '4240.000', 'l': '4220.000', 'c': '4222.000'}
        }
    ]
    
    for i, mock in enumerate(mock_signals, 1):
        print(f"\n📊 Test {i}/{len(mock_signals)}: {mock['granularity']} - {mock['signal']}")
        print(f"   C1 (Previous): {mock['c1']}")
        print(f"   C2 (Current):  {mock['c2']}")
        
        msg = f"[{mock['granularity']}] {mock['signal']}"
        print(f"   📤 Sending: {msg}")
        
        send_whatsapp_message(msg)
        
        print(f"   ✅ Message sent successfully!")
        
        # Wait 2 seconds between messages to avoid rate limiting
        if i < len(mock_signals):
            print(f"   ⏳ Waiting 2 seconds before next test...")
            time.sleep(2)
    
    print("\n" + "="*60)
    print("✅ WHATSAPP TEST COMPLETED!")
    print(f"📊 Total messages sent: {len(mock_signals)}")
    print("="*60 + "\n")

# --- CRT Signal Logic ---
def check_crt(c1, c2):
    # For testing: force specific signals
    if TEST_MODE and FORCE_CRT_SIGNAL == 'bullish':
        return "🟢 Bullish CRT"
    elif TEST_MODE and FORCE_CRT_SIGNAL == 'bearish':
        return "🔴 Bearish CRT"
    
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
    
    if TEST_MODE:
        print(f"🧪 [TEST] Candle data - C1: {c1}, C2: {c2}")
    
    print(c1, c2)
    result = check_crt(c1, c2)
    print(result)
    
    if result:
        msg = f"[{granularity}] {result}"
        print(msg)
        send_whatsapp_message(msg)

# --- Main loop ---
def run_crt_bot():
    # Track already processed signals to avoid duplicates
    processed_signals = set()
    
    while True:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        minute = now.minute
        second = now.second
        day_of_week = now.weekday()  # 0=Monday, 6=Sunday
        hour = now.hour
        
        print(f"Day: {day_of_week}, Hour: {hour}, Minute: {minute}, Second: {second}")
        
        # Check if we're in the allowed time window
        in_time_window = False
        
        # In test mode, always allow execution
        if TEST_MODE:
            in_time_window = True
        else:
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
        
        # Create unique key for this time slot to prevent duplicate signals
        time_key = f"{now.year}-{now.month}-{now.day}-{hour}-{minute//30}"
        
        # Only check at xx:30 and within time window
        if in_time_window and minute == 30 and 0 <= second <= 5:
            if time_key not in processed_signals:
                if now.hour % 1 == 0:
                    print("🚀 Fetching H1 candles...")
                    fetch_candles("H1")
                if now.hour % 4 == 0:
                    print("🚀 Fetching H4 candles...")
                    fetch_candles("H4")
                
                # Mark this time slot as processed
                processed_signals.add(time_key)
                
                # Clean up old entries (keep only last 10)
                if len(processed_signals) > 10:
                    processed_signals.pop()
        elif not in_time_window:
            print("⏸️ Outside trading hours - waiting...")
        
        time.sleep(1)

if __name__ == "__main__":
    # Check if WhatsApp test mode
    if TEST_WHATSAPP:
        test_whatsapp_messages()
        sys.exit(0)  # Exit after testing
    
    print("🚀 CRT Bot started... Waiting for H1/H4 candle closes...")
    
    if TEST_MODE:
        print("\n" + "="*50)
        print("TEST MODE INSTRUCTIONS:")
        print("="*50)
        print("1. Normal test: python app.py --test")
        print("2. Force bullish: Set FORCE_CRT_SIGNAL=bullish in .env")
        print("3. Force bearish: Set FORCE_CRT_SIGNAL=bearish in .env")
        print("4. ✅ WhatsApp messages WILL be sent in test mode")
        print("5. Test WhatsApp only: python app.py --testw")
        print("="*50 + "\n")

    # Start bot loop
    run_crt_bot()
