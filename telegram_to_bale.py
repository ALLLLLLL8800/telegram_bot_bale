import asyncio
import requests
import json
import re
import aiohttp

from datetime import datetime, timedelta
from telethon import TelegramClient

# =========================
# تنظیمات تلگرام
# =========================

CHANNELS = [
    'jangaaaran1390',
    'jangaavaran1390',
    'VahidOnline',
]

KEYWORDS = {
    "ایران", "آلمان", "فرانسه", "انگلیس", "آمریکا", "چین", "روسیه",
    "ترکیه", "عراق", "افغانستان", "اسرائیلی", "عربستان",
    "جمهوری اسلامی", "موشک", "پهباد", "شاهد", "تهران",
    "تلاویو", "رژیم", "ترامپ", "بایدن", "پوتین",
    "مکرون", "شی", "جین", "پینگ", "اردوغان",
    "نتانیاهو", "خامنه‌ای", "روحانی", "ظریف"
}

api_id = 5956396
api_hash = "f15432e1efa96bdcb6b1b3a87592f984"

# =========================
# تنظیمات بله
# =========================

BALE_TOKEN = "توکن_بله"
BALE_CHAT_ID = "ایدی_چت"

# =========================

client = TelegramClient(
    'my_session',
    api_id,
    api_hash,
    connection_retries=999999,
    retry_delay=5,
    auto_reconnect=True
)

LAST_IDS = {}
LAST_ID_FILE = 'last_ids.json'
sent_messages = []

# =========================
# ویرایش متن
# =========================

def edit_message_text(text):

    def replace(match):
        word = match.group(0)

        if word in KEYWORDS and len(word) >= 3:
            return word[:2] + "**" + word[2:]

        return word

    return re.sub(r'[A-Za-z\u0600-\u06FF]+', replace, text)

# =========================
# ذخیره آخرین آیدی
# =========================

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

# =========================
# ارسال به بله
# =========================

def send_to_bale(text, channel_name, index, total):

    edited = edit_message_text(text)

    try:

        msg = f"📢 کانال: {channel_name}\n📨 پیام {index}/{total}\n\n{edited}"

        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"

        response = requests.post(
            url,
            json={
                "chat_id": BALE_CHAT_ID,
                "text": msg
            },
            timeout=20
        )

        if response.status_code == 200:

            data = response.json()

            if data.get("ok"):

                message_id = data.get("result", {}).get("message_id")

                if message_id:

                    sent_messages.append({
                        'id': message_id,
                        'delete_at': datetime.now() + timedelta(minutes=15)
                    })

                print(f"✅ ارسال شد: {channel_name}")

                return True

    except Exception as e:

        print(f"❌ خطا بله: {e}")

    return False

# =========================
# حذف پیام بله
# =========================

def delete_from_bale(message_id):

    try:

        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/deleteMessage"

        response = requests.post(
            url,
            json={
                "chat_id": BALE_CHAT_ID,
                "message_id": message_id
            },
            timeout=20
        )

        if response.status_code == 200:

            data = response.json()

            if data.get("ok"):

                print(f"🗑 حذف شد: {message_id}")

                return True

    except Exception as e:

        print(f"⚠️ خطا حذف: {e}")

    return False

# =========================
# پاکسازی
# =========================

def cleanup_old_messages():

    now = datetime.now()

    for msg in sent_messages[:]:

        if msg['delete_at'] <= now:

            if delete_from_bale(msg['id']):

                sent_messages.remove(msg)

# =========================
# پردازش کانال
# =========================

async def process_channel(channel):

    last_id = LAST_IDS.get(channel)

    try:

        if last_id:

            messages = await client.get_messages(
                channel,
                min_id=last_id,
                limit=50
            )

        else:

            messages = await client.get_messages(
                channel,
                limit=10
            )

        text_messages = [msg for msg in messages if msg.text]

        if not text_messages:

            print(f"📭 {channel}")

            return 0

        text_messages.reverse()

        print(f"\n📨 {channel}: {len(text_messages)}")

        for i, msg in enumerate(text_messages, 1):

            send_to_bale(
                msg.text,
                channel,
                i,
                len(text_messages)
            )

            await asyncio.sleep(1)

        LAST_IDS[channel] = text_messages[-1].id

        save_last_ids()

        return len(text_messages)

    except Exception as e:

        print(f"❌ خطا کانال {channel}: {e}")

        return 0

# =========================
# همه کانال‌ها
# =========================

async def fetch_all_channels():

    total = 0

    for channel in CHANNELS:

        count = await process_channel(channel)

        total += count

        await asyncio.sleep(2)

    if total == 0:

        print(f"[{datetime.now().strftime('%H:%M:%S')}] پیام جدید نیست")

    else:

        print(f"✅ مجموع: {total}")

    cleanup_old_messages()

# =========================
# آب و هوا
# =========================

def weather_code_to_text(code):

    codes = {
        0: "☀️ صاف",
        1: "🌤 نیمه صاف",
        2: "⛅ ابری",
        3: "☁️ ابری",
        61: "🌧 باران",
        71: "❄️ برف",
        95: "⛈ رعد و برق"
    }

    return codes.get(code, "🌈 متغیر")

async def fetch_weather_async(lat, lon, city_name):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "weathercode"
        ],
        "timezone": "auto",
        "forecast_days": 5
    }

    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        try:

            async with session.get(url, params=params) as resp:

                data = await resp.json()

        except Exception as e:

            print(f"❌ خطا آب و هوا: {e}")

            return None

    current = data.get("current_weather", {})
    daily = data.get("daily", {})

    forecast = []

    for i in range(len(daily.get("time", []))):

        forecast.append({
            "date": daily["time"][i],
            "min": daily["temperature_2m_min"][i],
            "max": daily["temperature_2m_max"][i],
            "code": daily["weathercode"][i]
        })

    return {
        "city": city_name,
        "temp": current.get("temperature"),
        "wind": current.get("windspeed"),
        "code": current.get("weathercode"),
        "forecast": forecast
    }

async def send_weather_update():

    cities = {
        "تهران": {"lat": 35.6892, "lon": 51.3890},
        "گناباد": {"lat": 34.3529, "lon": 58.6837}
    }

    msg = "🌤 گزارش آب و هوا\n\n"

    for city, coords in cities.items():

        data = await fetch_weather_async(
            coords["lat"],
            coords["lon"],
            city
        )

        if not data:
            continue

        msg += f"📍 {city}\n"
        msg += f"🌡 دما: {data['temp']}°C\n"
        msg += f"💨 باد: {data['wind']} km/h\n"
        msg += f"{weather_code_to_text(data['code'])}\n\n"

    try:

        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"

        requests.post(
            url,
            json={
                "chat_id": BALE_CHAT_ID,
                "text": msg
            },
            timeout=20
        )

        print("✅ آب و هوا ارسال شد")

    except Exception as e:

        print(f"❌ خطا ارسال آب و هوا: {e}")

# =========================
# حلقه آب و هوا
# =========================

async def weather_loop():

    await asyncio.sleep(10)

    while True:

        await send_weather_update()

        await asyncio.sleep(24 * 60 * 60)

# =========================
# پاکسازی
# =========================

async def cleanup_task():

    while True:

        cleanup_old_messages()

        await asyncio.sleep(60)

# =========================
# MAIN
# =========================

async def main():

    load_last_ids()

    await client.start()

    me = await client.get_me()

    print(f"✅ ورود: {me.first_name}")

    await fetch_all_channels()

    asyncio.create_task(cleanup_task())

    asyncio.create_task(weather_loop())

    while True:

        try:

            now = datetime.now()

            hour = now.hour

            if 0 <= hour < 6:

                print("😴 خواب شب")

                await asyncio.sleep(60 * 60)

                continue

            print(f"⏳ {now.strftime('%H:%M:%S')}")

            await asyncio.sleep(60 * 60)

            await fetch_all_channels()

        except Exception as e:

            print(f"❌ خطا اصلی: {e}")

            await asyncio.sleep(30)

# =========================

if __name__ == "__main__":

    asyncio.run(main())