import asyncio
import requests
import json
import re
import aiohttp
from datetime import datetime, timedelta
from telethon import TelegramClient

# ========== تنظیمات تلگرام ==========
CHANNELS = [
    'jangaaaran1390',
    'jangaavaran1390',
    'VahidOnline',
]

KEYWORDS = {
    "ایران", "آلمان", "فرانسه", "انگلیس", "آمریکا", "چین", "روسیه", "ترکیه", "عراق", "افغانستان",
    "اسرائیلی", "عربستان", "جمهوری اسلامی", "موشک", "پهباد", "شاهد", "تهران", "تلاویو", "رژیم",
    "ترامپ", "بایدن", "پوتین", "مکرون", "شی", "جین", "پینگ", "اردوغان", "نتانیاهو", "خامنه‌ای", "روحانی", "ظریف"
}

# ========== تنظیمات تلگرام ==========
api_id = 5956396
api_hash = "f15432e1efa96bdcb6b1b3a87592f984"
CHANNEL_USERNAME = 'jangaavaran1390'

# ========== تنظیمات بله ==========
BALE_TOKEN = "1825880479:SKAT3qpdRSp5gtx1YYvmR_hgR4TvvQUNN2U"
BALE_CHAT_ID = "5227164458"
# ================================

# ایجاد کلاینت تلگرام بدون پروکسی (برای سرور خارج)
client = TelegramClient('my_session', api_id, api_hash)
LAST_IDS = {}
LAST_ID_FILE = 'last_ids.json'
sent_messages = []

# ================== توابع اصلی ==================
def edit_message_text(text):
    def replace(match):
        word = match.group(0)
        if word in KEYWORDS and len(word) >= 3:
            return word[:2] + "**" + word[2:]
        return word
    return re.sub(r'[A-Za-z\u0600-\u06FF]+', replace, text)

def load_last_ids():
    global LAST_IDS
    try:
        with open(LAST_ID_FILE, 'r') as f:
            LAST_IDS = json.load(f)
    except:
        LAST_IDS = {}

def save_last_ids():
    with open(LAST_ID_FILE, 'w') as f:
        json.dump(LAST_IDS, f)

def send_to_bale(text, channel_name, index, total):
    edited = edit_message_text(text)
    try:
        msg_with_number = f"📢 کانال: {channel_name}\n📨 پیام {index}/{total}\n\n{edited}"
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": BALE_CHAT_ID,
            "text": msg_with_number
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                message_id = data.get("result", {}).get("message_id")
                if message_id:
                    sent_messages.append({
                        'id': message_id,
                        'delete_at': datetime.now() + timedelta(minutes=15)
                    })
                print(f"   ✅ پیام {index} از {channel_name} ارسال شد (ID: {message_id})")
                return True
    except Exception as e:
        print(f"   ❌ خطا: {e}")
    return False

def delete_from_bale(message_id):
    try:
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/deleteMessage"
        response = requests.post(url, json={
            "chat_id": BALE_CHAT_ID,
            "message_id": message_id
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                print(f"   🗑️ پیام {message_id} از بله حذف شد")
                return True
    except Exception as e:
        print(f"   ⚠️ خطا در حذف: {e}")
    return False

def cleanup_old_messages():
    now = datetime.now()
    deleted_count = 0
    for msg in sent_messages[:]:
        if msg['delete_at'] <= now:
            if delete_from_bale(msg['id']):
                sent_messages.remove(msg)
                deleted_count += 1
    if deleted_count:
        print(f"   🧹 {deleted_count} پیام از بله پاک شد")
    return deleted_count

async def process_channel(channel):
    last_id = LAST_IDS.get(channel, None)
    if last_id:
        messages = await client.get_messages(channel, min_id=last_id, limit=50)
    else:
        messages = await client.get_messages(channel, limit=10)
    text_messages = [msg for msg in messages if msg.text]
    if not text_messages:
        print(f"📭 {channel}: پیام جدیدی نیست")
        return 0
    text_messages.reverse()
    print(f"\n📨 {channel}: {len(text_messages)} پیام جدید:")
    for i, msg in enumerate(text_messages, 1):
        print(f"   {i}. {msg.text[:50]}...")
        send_to_bale(msg.text, channel, i, len(text_messages))
        await asyncio.sleep(1)
    LAST_IDS[channel] = text_messages[-1].id
    save_last_ids()
    return len(text_messages)

async def fetch_all_channels():
    total = 0
    for channel in CHANNELS:
        try:
            count = await process_channel(channel)
            total += count
        except Exception as e:
            print(f"❌ خطا در کانال {channel}: {e}")
        await asyncio.sleep(2)
    if total == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📭 هیچ پیام جدیدی نیست")
    else:
        print(f"\n✅ مجموعاً {total} پیام جدید ارسال شد")
    cleanup_old_messages()
    return total

async def cleanup_task():
    while True:
        await asyncio.sleep(60)
        if sent_messages:
            cleanup_old_messages()

# ================== توابع آب و هوا (بدون پروکسی) ==================
async def fetch_weather_async(lat, lon, city_name):
    """دریافت پیش‌بینی امروز و ۱۰ روز آینده از Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "windspeed_10m_max", "weathercode"],
        "current_weather": "true",
        "timezone": "auto",
        "forecast_days": 10
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"❌ خطا در دریافت آب و هوای {city_name}: {resp.status}")
                    return None
                data = await resp.json()
        except Exception as e:
            print(f"❌ خطا در اتصال به Open-Meteo برای {city_name}: {e}")
            return None
    
    # پردازش داده‌ها
    current = data.get("current_weather", {})
    today_temp = current.get("temperature")
    today_wind = current.get("windspeed")
    weather_code = current.get("weathercode")
    
    daily = data.get("daily", {})
    forecast = []
    if daily:
        for i in range(min(10, len(daily.get("time", [])))):
            forecast.append({
                "date": daily["time"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "temp_max": daily["temperature_2m_max"][i],
                "precip": daily["precipitation_sum"][i],
                "wind": daily["windspeed_10m_max"][i],
                "code": daily["weathercode"][i]
            })
    
    return {
        "city": city_name,
        "today_temp": today_temp,
        "today_wind": today_wind,
        "weather_code": weather_code,
        "forecast": forecast
    }

def weather_code_to_text(code):
    codes = {
        0: "☀️ صاف",
        1: "🌤️ عمدتاً صاف",
        2: "⛅ نیمه ابری",
        3: "☁️ ابری",
        45: "🌫️ غبارآلود",
        51: "🌧️ نم نم باران",
        53: "🌧️ باران خفیف",
        55: "🌧️ باران مداوم",
        61: "🌧️ باران",
        63: "🌧️🌧️ باران شدید",
        71: "❄️ برف",
        73: "❄️ برف متوسط",
        75: "❄️❄️ کولک",
        80: "🌦️ رگبار",
        95: "⛈️ رعد و برق"
    }
    return codes.get(code, "🌈 متغیر")

async def send_weather_update():
    """دریافت آب و هوا برای تهران و گناباد، ارسال به بله و پین کردن"""
    cities = {
        "تهران": {"lat": 35.6892, "lon": 51.3890},
        "گناباد": {"lat": 34.3529, "lon": 58.6837}
    }
    
    weather_data = {}
    for name, coords in cities.items():
        data = await fetch_weather_async(coords["lat"], coords["lon"], name)
        if data:
            weather_data[name] = data
        else:
            print(f"⚠️ داده‌ای برای {name} دریافت نشد")
    
    if not weather_data:
        print("⚠️ هیچ داده آب و هوایی دریافت نشد. ارسال نمی‌شود.")
        return
    
    # ساخت متن پیام
    msg = "🌍 **پیش‌بینی آب و هوای امروز و ۱۰ روز آینده**\n\n"
    for city, w in weather_data.items():
        msg += f"📍 **{city}**\n"
        msg += f"☀️ امروز: {w['today_temp']}°C  |  💨 باد: {w['today_wind']} km/h  |  {weather_code_to_text(w['weather_code'])}\n"
        msg += "📅 **پیش‌بینی ۱۰ روزه (۵ روز اول):**\n"
        for day in w['forecast'][:5]:
            msg += f"   {day['date']}: {day['temp_min']}°~{day['temp_max']}°C  |  🌧️{day['precip']}mm  |  {weather_code_to_text(day['code'])}\n"
        if len(w['forecast']) > 5:
            msg += f"   ... و {len(w['forecast'])-5} روز دیگر\n"
        msg += "\n"
    
    msg += "🕒 _به‌روزرسانی خودکار هر ۲۴ ساعت_"
    
    # ارسال به بله
    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    payload = {
        "chat_id": BALE_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                message_id = data.get("result", {}).get("message_id")
                if message_id:
                    # پین کردن پیام
                    pin_url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/pinChatMessage"
                    pin_payload = {
                        "chat_id": BALE_CHAT_ID,
                        "message_id": message_id
                    }
                    pin_resp = requests.post(pin_url, json=pin_payload, timeout=10)
                    if pin_resp.status_code == 200:
                        print("✅ پیام آب و هوا ارسال و پین شد")
                    else:
                        print(f"⚠️ پین نشد: {pin_resp.text}")
                else:
                    print("⚠️ پیام ارسال شد اما message_id دریافت نشد")
            else:
                print(f"❌ خطا در ارسال آب و هوا: {data}")
        else:
            print(f"❌ خطا: {resp.status_code}")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام آب و هوا: {e}")

async def weather_loop():
    """تسک هر ۲۴ ساعت یک بار (اولین بار ۱۰ ثانیه بعد از شروع)"""
    await asyncio.sleep(10)
    while True:
        await send_weather_update()
        await asyncio.sleep(24 * 60 * 60)

# ================== تابع اصلی ==================
async def main():
    load_last_ids()
    await client.start()
    me = await client.get_me()
    print(f"✅ سلام {me.first_name}!")
    print(f"📺 تعداد کانال‌ها: {len(CHANNELS)}")
    for ch in CHANNELS:
        last = LAST_IDS.get(ch, 'ندارد')
        print(f"   - {ch} (آخرین ID: {last})")
    print(f"🤖 بله: فعال")
    print(f"🗑️ حذف پیام‌های بله بعد از 15 دقیقه")
    print(f"⏰ هر 1 ساعت یکبار چک می‌شود (به جز 12 شب تا 6 صبح)")
    print("🌤️ آب و هوا: هر 24 ساعت یکبار ارسال و پین می‌شود")
    print("=" * 50)
    
    await fetch_all_channels()
    asyncio.create_task(cleanup_task())
    asyncio.create_task(weather_loop())
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        if 0 <= current_hour < 6:
            wakeup = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= wakeup:
                sleep_sec = 0
            else:
                sleep_sec = (wakeup - now).total_seconds()
            print(f"😴 زمان خواب (ساعت {current_hour}) - تا ساعت 6 صبح می‌خوابم ({sleep_sec/60:.0f} دقیقه)")
            await asyncio.sleep(sleep_sec)
            print("🌅 بیدار شدن در ساعت 6 صبح - دریافت پیام‌های 6 ساعت گذشته...")
            await fetch_all_channels()
            continue
        print(f"\n⏳ صبر تا 1 ساعت بعد... ({now.strftime('%H:%M:%S')})")
        await asyncio.sleep(60 * 60)
        print(f"\n🔄 اجرای مجدد در {datetime.now().strftime('%H:%M:%S')}")
        await fetch_all_channels()

if __name__ == "__main__":
    asyncio.run(main())
