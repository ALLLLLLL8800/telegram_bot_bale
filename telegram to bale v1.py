import asyncio
import requests
import json
import re
from datetime import datetime, timedelta
from telethon import TelegramClient
import traceback

# ========== Telegram Settings ==========
CHANNELS = [
    'mamlekate',
    'jangaavaran1390',
    'VahidOnline',
]

KEYWORDS = {
    "ایران", "آلمان", "فرانسه", "انگلیس", "آمریکا", "چین", "روسیه", "ترکیه", "عراق", "افغانستان",
    "اسرائیلی", "عربستان", "جمهوری اسلامی", "موشک", "پهباد", "شاهد", "تهران", "تلاویو", "رژیم",
    "ترامپ", "بایدن", "پوتین", "مکرون", "شی", "جین", "پینگ", "اردوغان", "نتانیاهو", "خامنه‌ای", "روحانی", "ظریف"
}

api_id = 5956396
api_hash = "f15432e1efa96bdcb6b1b3a87592f984"
CHANNEL_USERNAME = 'jangaavaran1390'

# ========== Bale Settings ==========
BALE_TOKEN = "1825880478:SKAT3qpdRSp5gtx1YYvmR_hgR4TvvQUNN2U"
BALE_CHAT_ID = "5227164458"
# ===================================

client = TelegramClient('my_session', api_id, api_hash)
LAST_IDS = {}
LAST_ID_FILE = 'last_ids.json'
sent_messages = []

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
        msg_with_number = f"📢 Channel: {channel_name}\n📨 Message {index}/{total}\n\n{edited}"
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
                print(f"   [OK] Message {index} from {channel_name} sent (ID: {message_id})")
                return True
    except Exception as e:
        print(f"   [ERROR] {e}")
    return False

def send_error_to_bale(error_msg):
    try:
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        payload = {
            "chat_id": BALE_CHAT_ID,
            "text": f"⚠️ Bot Error:\n{error_msg}"
        }
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def send_no_news_to_bale():
    try:
        url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
        payload = {
            "chat_id": BALE_CHAT_ID,
            "text": "📭 No new messages from any channel in the last hour."
        }
        requests.post(url, json=payload, timeout=10)
    except:
        pass

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
                print(f"   [DELETED] Message {message_id} removed from Bale")
                return True
    except Exception as e:
        print(f"   [ERROR] Delete failed: {e}")
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
        print(f"   [CLEANUP] {deleted_count} messages deleted from Bale")
    return deleted_count

async def process_channel(channel):
    last_id = LAST_IDS.get(channel, None)
    if last_id:
        messages = await client.get_messages(channel, min_id=last_id, limit=50)
    else:
        messages = await client.get_messages(channel, limit=10)
    text_messages = [msg for msg in messages if msg.text]
    if not text_messages:
        print(f"[{channel}] No new messages")
        return 0
    text_messages.reverse()
    print(f"\n[{channel}] {len(text_messages)} new messages:")
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
            error_trace = traceback.format_exc()
            print(f"[ERROR] Channel {channel}: {e}")
            send_error_to_bale(f"Channel {channel}: {str(e)}\n{error_trace}")
        await asyncio.sleep(2)
    if total == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No new messages from any channel")
        send_no_news_to_bale()
    else:
        print(f"\n[SUMMARY] Total {total} new messages sent")
    cleanup_old_messages()
    return total

async def cleanup_task():
    while True:
        await asyncio.sleep(60)
        if sent_messages:
            cleanup_old_messages()

async def main():
    load_last_ids()
    await client.start()
    me = await client.get_me()
    print(f"[OK] Hello {me.first_name}!")
    print(f"[INFO] Channels: {len(CHANNELS)}")
    for ch in CHANNELS:
        last = LAST_IDS.get(ch, 'None')
        print(f"   - {ch} (Last ID: {last})")
    print(f"[INFO] Bale: Active")
    print(f"[INFO] Auto-delete Bale messages after 15 minutes")
    print(f"[INFO] Will check exactly at each hour (except 00:00-06:00)")
    print("=" * 50)

    # First run immediately
    await fetch_all_channels()

    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_second = now.second

        # Sleep until next hour (or 6:00 if within 00-06)
        if 0 <= current_hour < 6:
            # Sleeping until 06:00:00 today
            target = now.replace(hour=6, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            print(f"[SLEEP] Night period ({current_hour}:00-06:00) - Sleeping until 06:00 ({sleep_seconds/60:.0f} minutes)")
            await asyncio.sleep(sleep_seconds)
            print("[WAKE] Woke up at 06:00 - Fetching accumulated messages...")
            await fetch_all_channels()
            continue
        else:
            # Sleep until next exact hour
            next_hour = current_hour + 1
            target = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            if next_hour == 24:
                target += timedelta(days=1)
                target = target.replace(hour=0, minute=0, second=0, microsecond=0)
            sleep_seconds = (target - now).total_seconds()
            print(f"[SLEEP] Next check at {target.strftime('%H:%M:%S')} (in {sleep_seconds/60:.1f} minutes)")
            await asyncio.sleep(sleep_seconds)
            print(f"\n[RUN] Executing at {datetime.now().strftime('%H:%M:%S')}")
            await fetch_all_channels()

if __name__ == "__main__":
    asyncio.run(main())
