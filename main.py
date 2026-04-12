import os
import time
import yt_dlp
import requests
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread

# --- CONFIG ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

CHANNELS = [
    {"id": "@TheDubbedStationBD", "link": "https://t.me/TheDubbedStationBD", "name": "Main Channel"},
]

POST_CHANNELS = ["@TheDubbedStationBD"]

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), parse_mode="HTML")

# --- DB ---
client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

# --- FLASK ---
app = Flask(__name__)

@app.route('/')
def home():
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))))
    t.daemon = True
    t.start()

# --- FORCE JOIN ---
def is_joined(user_id):
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id

    users_col.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {"user_id": user_id}},
        upsert=True
    )

    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
        markup.add(types.InlineKeyboardButton("🔄 চেক করুন", callback_data="check_join"))
        bot.send_message(user_id, "⚠️ চ্যানেলে জয়েন না করলে বট কাজ করবে না!", reply_markup=markup)
        return

    show_main_menu(user_id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "💰 Earning", "📊 Stats")
    bot.send_message(chat_id, "👋 MediaGo Hub-এ স্বাগতম!", reply_markup=markup)

# --- JOIN CHECK ---
@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if is_joined(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ এখনো জয়েন করেননি!", show_alert=True)

# =====================================================
# 🔥 SUPER FAST HYBRID DOWNLOADER START
# =====================================================

MAX_MB = 40

@bot.message_handler(func=lambda m: m.text and any(x in m.text for x in ["facebook.com","tiktok.com","youtube.com","youtu.be","instagram.com"]))
def handle_downloader(message):
    user_id = message.chat.id
    url = message.text

    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"last_url": url, "time": int(time.time())}},
        upsert=True
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Watch Ad (1 Min)", url="https://omg10.com/4/10651831"))
    markup.add(types.InlineKeyboardButton("🔓 Unlock Now", callback_data="unlock_video"))

    bot.send_message(message.chat.id, "🔒 ভিডিও লক করা আছে!\n\n১ মিনিট অ্যাড দেখুন তারপর Unlock করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "unlock_video")
def unlock_video(call):
    user = users_col.find_one({"user_id": call.from_user.id})

    if not user:
        bot.answer_callback_query(call.id, "❌ ডাটা নাই!")
        return

    now = int(time.time())
    if now - user.get("time", 0) < 60:
        remain = 60 - (now - user.get("time", 0))
        bot.answer_callback_query(call.id, f"⏳ {remain} সেকেন্ড অপেক্ষা করুন!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📥 Download Now", callback_data="download_video"))

    bot.edit_message_text("✅ আনলক হয়েছে!\n\nডাউনলোড করুন 👇",
                          call.message.chat.id,
                          call.message.message_id,
                          reply_markup=markup)

def get_tiktok_fast(url):
    try:
        r = requests.get(f"https://api.tiklydown.eu.org/api/download?url={url}", timeout=8).json()
        return r.get("video", {}).get("noWatermark")
    except:
        return None

@bot.callback_query_handler(func=lambda call: call.data == "download_video")
def download_video(call):
    user = users_col.find_one({"user_id": call.from_user.id})

    if not user or "last_url" not in user:
        bot.send_message(call.message.chat.id, "❌ ভিডিও নাই!")
        return

    url = user["last_url"]
    msg = bot.send_message(call.message.chat.id, "⚡ Processing...")

    try:
        # TikTok fast
        if "tiktok.com" in url:
            fast = get_tiktok_fast(url)
            if fast:
                bot.send_video(call.message.chat.id, fast, caption="⚡ Instant Ready!")
                bot.delete_message(call.message.chat.id, msg.message_id)
                return

        # yt-dlp
        file = f"{call.from_user.id}.mp4"

        ydl_opts = {
            'format': 'best[height<=480]',
            'outtmpl': file,
            'quiet': True,
            'noplaylist': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        size = os.path.getsize(file) / (1024 * 1024)

        if size <= MAX_MB:
            with open(file, 'rb') as v:
                bot.send_video(call.message.chat.id, v, caption="✅ Ready!")
        else:
            bot.send_message(call.message.chat.id, f"📥 বড় ভিডিও ({int(size)}MB)\n\nডাউনলোড করুন:\n{url}")

        if os.path.exists(file):
            os.remove(file)

        bot.delete_message(call.message.chat.id, msg.message_id)

    except:
        bot.send_message(call.message.chat.id, "❌ Failed!")

# =====================================================
# 🔥 DOWNLOADER END
# =====================================================

# --- ADMIN POST ---
@bot.message_handler(commands=['post'])
def admin_post(message):
    if message.from_user.id != ADMIN_ID:
        return

    raw_text = message.caption if message.caption else message.text
    if not raw_text:
        return

    content_text = raw_text.replace("/post", "").strip()
    data = [x.strip() for x in content_text.split("|")]

    if len(data) < 4:
        bot.reply_to(message, "❌ Format: name | category | image | link")
        return

    name, cat, img, link = data

    content_col.insert_one({
        "name": name,
        "category": cat.lower(),
        "image": img,
        "link": link
    })

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Watch", url=f"https://t.me/{bot.get_me().username}?start=search"))

    for ch in POST_CHANNELS:
        try:
            bot.send_photo(ch, img, caption=f"🎬 {name}\n📂 {cat}", reply_markup=markup)
        except:
            pass

    bot.reply_to(message, "✅ Posted!")

# --- STATS ---
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    total = users_col.count_documents({})
    bot.reply_to(message, f"📊 Users: {total}")

# --- RUN ---
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
