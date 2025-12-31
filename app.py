import oandapyV20
from oandapyV20.endpoints.instruments import InstrumentsCandles
from datetime import datetime, timedelta, timezone
from twilio.rest import Client
import time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os
import sys
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
import asyncio

load_dotenv()

ACCESS_TOKEN = os.getenv('OANDA_ACCESS_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
TO_WHATSAPP_NUMBER = os.getenv('TO_WHATSAPP_NUMBER')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Testing mode configuration
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true' or '--test' in sys.argv
FORCE_CRT_SIGNAL = os.getenv('FORCE_CRT_SIGNAL', 'none').lower()
TEST_WHATSAPP = '--testw' in sys.argv
TEST_TELEGRAM = '--testt' in sys.argv

if TEST_MODE:
    print("⚠️ TEST MODE ENABLED ⚠️")
    if FORCE_CRT_SIGNAL != 'none':
        print(f"🧪 Forcing {FORCE_CRT_SIGNAL.upper()} CRT signals")

if TEST_WHATSAPP:
    print("📱 WHATSAPP TEST MODE ENABLED 📱")

if TEST_TELEGRAM:
    print("📱 TELEGRAM TEST MODE ENABLED 📱")

client = oandapyV20.API(access_token=ACCESS_TOKEN, environment="practice")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Global variable for Telegram app
telegram_app = None

# --- Load/Save Authorized Users ---
USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('authorized_users', []))
    except FileNotFoundError:
        return set()
    except json.JSONDecodeError:
        print("⚠️ Error reading users.json, creating new file")
        return set()

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump({'authorized_users': list(users)}, f, indent=2)

authorized_users = load_users()

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    if user_id not in authorized_users:
        authorized_users.add(user_id)
        save_users(authorized_users)
        await update.message.reply_text(
            f"✅ Welcome {username}!\n"
            f"🎉 You're now subscribed to CRT signals!\n"
            f"📊 You'll receive H1 and H4 CRT notifications.\n\n"
            f"Your User ID: `{user_id}`",
            parse_mode='Markdown'
        )
        print(f"✅ New user subscribed: {username} (ID: {user_id})")
    else:
        await update.message.reply_text(
            f"👋 Welcome back {username}!\n"
            f"✅ You're already subscribed to CRT signals.\n\n"
            f"Your User ID: `{user_id}`",
            parse_mode='Markdown'
        )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    if user_id in authorized_users:
        authorized_users.remove(user_id)
        save_users(authorized_users)
        await update.message.reply_text(
            f"👋 Goodbye {username}!\n"
            f"❌ You've been unsubscribed from CRT signals."
        )
        print(f"❌ User unsubscribed: {username} (ID: {user_id})")
    else:
        await update.message.reply_text("⚠️ You're not subscribed.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_subscribed = user_id in authorized_users
    total_users = len(authorized_users)
    
    status_msg = (
        f"📊 **CRT Bot Status**\n\n"
        f"Your Status: {'✅ Subscribed' if is_subscribed else '❌ Not Subscribed'}\n"
        f"Total Subscribers: {total_users}\n"
        f"Your User ID: `{user_id}`"
    )
    await update.message.reply_text(status_msg, parse_mode='Markdown')

# --- Send Telegram message to all authorized users ---
async def send_telegram_message(message):
    if not telegram_app or not authorized_users:
        print("⚠️ No Telegram app or no subscribers")
        return
    
    success_count = 0
    fail_count = 0
    
    users_list = list(authorized_users)
    
    for user_id in users_list:
        try:
            await telegram_app.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception as e:
            print(f"❌ Failed to send Telegram to {user_id}: {e}")
            fail_count += 1
    
    if TEST_MODE or TEST_TELEGRAM:
        print(f"🧪 [TEST] Telegram sent to {success_count}/{len(authorized_users)} users")
    else:
        print(f"📤 Telegram sent to {success_count} users (Failed: {fail_count})")

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

# --- Unified message sender (Telegram first, then WhatsApp) ---
async def send_notification(message):
    try:
        await send_telegram_message(message)
    except Exception as e:
        print(f"⚠️ Telegram failed: {e}")
    
    try:
        send_whatsapp_message(message)
    except Exception as e:
        print(f"⚠️ WhatsApp failed (continuing): {e}")

# --- Test Telegram with mock data ---
async def test_telegram_messages():
    print("\n" + "="*60)
    print("🧪 TESTING TELEGRAM MESSAGING WITH MOCK DATA")
    print("="*60 + "\n")
    
    mock_signals = [
        "[H1] 🟢 Bullish CRT",
        "[H1] 🔴 Bearish CRT",
        "[H4] 🟢 Bullish CRT",
        "[H4] 🔴 Bearish CRT"
    ]
    
    for i, msg in enumerate(mock_signals, 1):
        print(f"\n📊 Test {i}/{len(mock_signals)}: {msg}")
        print(f"   📤 Sending to {len(authorized_users)} users...")
        
        await send_telegram_message(msg)
        
        print(f"   ✅ Message sent successfully!")
        
        if i < len(mock_signals):
            print(f"   ⏳ Waiting 2 seconds before next test...")
            await asyncio.sleep(2)
    
    print("\n" + "="*60)
    print("✅ TELEGRAM TEST COMPLETED!")
    print(f"📊 Total messages sent: {len(mock_signals)}")
    print(f"👥 Subscribers: {len(authorized_users)}")
    print("="*60 + "\n")

# --- Test WhatsApp with mock data ---
def test_whatsapp_messages():
    print("\n" + "="*60)
    print("🧪 TESTING WHATSAPP MESSAGING WITH MOCK DATA")
    print("="*60 + "\n")
    
    mock_signals = [
        {"granularity": "H1", "signal": "🟢 Bullish CRT"},
        {"granularity": "H1", "signal": "🔴 Bearish CRT"}
    ]
    
    for i, mock in enumerate(mock_signals, 1):
        print(f"\n📊 Test {i}/{len(mock_signals)}: {mock['granularity']} - {mock['signal']}")
        
        msg = f"[{mock['granularity']}] {mock['signal']}"
        print(f"   📤 Sending: {msg}")
        
        send_whatsapp_message(msg)
        
        print(f"   ✅ Message sent successfully!")
        
        if i < len(mock_signals):
            print(f"   ⏳ Waiting 2 seconds before next test...")
            time.sleep(2)
    
    print("\n" + "="*60)
    print("✅ WHATSAPP TEST COMPLETED!")
    print(f"📊 Total messages sent: {len(mock_signals)}")
    print("="*60 + "\n")

# --- CRT Signal Logic ---
def check_crt(c1, c2):
    if TEST_MODE and FORCE_CRT_SIGNAL == 'bullish':
        return "🟢 Bullish CRT"
    elif TEST_MODE and FORCE_CRT_SIGNAL == 'bearish':
        return "🔴 Bearish CRT"
    
    l1 = float(c1['l'])
    h1 = float(c1['h'])
    close1 = float(c1['c'])

    l2 = float(c2['l'])
    h2 = float(c2['h'])
    close2 = float(c2['c'])

    if l1 > l2 and close2 > l1 and h1 > h2:
        return "🟢 Bullish CRT"
    elif h1 < h2 and close2 < h1 and l1 < l2:
        return "🔴 Bearish CRT"
    return None

# --- Fetch 3 candles and evaluate signal ---
async def fetch_candles(granularity):
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
    
    c1 = candles[0]['mid']
    c2 = candles[1]['mid']
    
    if TEST_MODE:
        print(f"🧪 [TEST] C1 (setup): {c1}, C2 (sweep): {c2}")
    
    result = check_crt(c1, c2)
    
    if result:
        msg = f"[{granularity}] {result}"
        print(msg)
        await send_notification(msg)

# --- Main loop with Telegram bot ---
async def run_bot():
    global telegram_app
    
    # Initialize Telegram bot with retry logic
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        print("🤖 Starting Telegram bot...")
        
        try:
            request = HTTPXRequest(
                connection_pool_size=8,
                connect_timeout=10.0,
                read_timeout=10.0,
                write_timeout=10.0,
                pool_timeout=10.0
            )
            
            telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
            
            telegram_app.add_handler(CommandHandler("start", start))
            telegram_app.add_handler(CommandHandler("stop", stop))
            telegram_app.add_handler(CommandHandler("status", status))
            
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling(drop_pending_updates=True)
            print(f"✅ Telegram bot ready! Current subscribers: {len(authorized_users)}")
        except Exception as e:
            print(f"⚠️ Telegram bot initialization failed: {e}")
            print("📱 Bot will continue with WhatsApp only")
            telegram_app = None
    else:
        print("⚠️ TELEGRAM_BOT_TOKEN not configured")
    
    print("🚀 CRT Bot started... Waiting for H1/H4 candle closes...")
    
    # Main CRT detection loop
    processed_signals = set()
    
    while True:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        minute = now.minute
        second = now.second
        day_of_week = now.weekday()
        hour = now.hour
        
        print(f"Day: {day_of_week}, Hour: {hour}, Minute: {minute}, Second: {second}")
        
        in_time_window = False
        
        if TEST_MODE:
            in_time_window = True
        else:
            if day_of_week == 0:
                if hour >= 3 or hour == 0:
                    in_time_window = True
            elif 1 <= day_of_week <= 3:
                in_time_window = True
            elif day_of_week == 4:
                if hour <= 0 and minute <= 10:
                    in_time_window = True
                elif hour >= 3:
                    in_time_window = True
        
        time_key = f"{now.year}-{now.month}-{now.day}-{hour}-{minute//30}"
        
        if in_time_window and minute == 30 and 0 <= second <= 5:
            if time_key not in processed_signals:
                if now.hour % 1 == 0:
                    print("🚀 Fetching H1 candles...")
                    await fetch_candles("H1")
                if now.hour % 4 == 0:
                    print("🚀 Fetching H4 candles...")
                    await fetch_candles("H4")
                
                processed_signals.add(time_key)
                
                if len(processed_signals) > 10:
                    processed_signals.pop()
        elif not in_time_window:
            print("⏸️ Outside trading hours - waiting...")
        
        await asyncio.sleep(1)

# --- Test mode for Telegram ---
async def run_telegram_test():
    global telegram_app
    
    print("🤖 Starting Telegram bot for testing...")
    
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("stop", stop))
    telegram_app.add_handler(CommandHandler("status", status))
    
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling(drop_pending_updates=True)
    
    print(f"✅ Telegram bot ready! Current subscribers: {len(authorized_users)}")
    
    await asyncio.sleep(2)
    await test_telegram_messages()
    
    await telegram_app.updater.stop()
    await telegram_app.stop()
    await telegram_app.shutdown()

if __name__ == "__main__":
    if TEST_TELEGRAM:
        asyncio.run(run_telegram_test())
        sys.exit(0)
    
    if TEST_WHATSAPP:
        test_whatsapp_messages()
        sys.exit(0)
    
    if TEST_MODE:
        print("\n" + "="*50)
        print("TEST MODE INSTRUCTIONS:")
        print("="*50)
        print("1. Normal test: python app.py --test")
        print("2. Force bullish: Set FORCE_CRT_SIGNAL=bullish in .env")
        print("3. Force bearish: Set FORCE_CRT_SIGNAL=bearish in .env")
        print("4. Test WhatsApp: python app.py --testw")
        print("5. Test Telegram: python app.py --testt")
        print("="*50 + "\n")
    
    asyncio.run(run_bot())
