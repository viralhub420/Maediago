import os
import time
import telebot
import yt_dlp
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread

# --- Flask & Database Setup ---
app = Flask(__name__)
client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

@app.route('/')
def home():
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def run():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Bot Config ---
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ---------------- DOWNLOADER LOGIC (New) ----------------
@bot.message_handler(func=lambda m: m.text and ("facebook.com" in m.text or "tiktok.com" in m.text or "youtube.com" in m.text or "youtu.be" in m.text or "instagram.com" in m.text))
def handle_download(message):
    chat_id = message.chat.id
    url = message.text
    msg = bot.send_message(chat_id, "⏳ ভিডিওটি প্রসেস করা হচ্ছে, দয়া করে অপেক্ষা করুন...")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'video_{chat_id}.mp4',
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = f'video_{chat_id}.mp4'
            
            with open(filename, 'rb') as f:
                bot.send_video(chat_id, f, caption=f"✅ ডাউনলোড সফল!\n🎬 {info.get('title')}")
            
            if os.path.exists(filename): os.remove(filename)
            bot.delete_message(chat_id, msg.message_id)
            
    except Exception as e:
        bot.edit_message_text(f"❌ এরর: ভিডিওটি ডাউনলোড করা যাচ্ছে না। লিঙ্কটি চেক করুন।", chat_id, msg.message_id)

# ---------------- START & MENU (Original) ----------------
@bot.message_handler(commands=['start'])
def start(message):
    if not users_col.find_one({"user_id": message.chat.id}):
        users_col.insert_one({"user_id": message.chat.id})

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "📺 Dramas")
    markup.row("🎭 Series", "🔍 Search")

    bot.send_message(message.chat.id, "👋 MediaGo Hub-এ স্বাগতম!\nভিডিও ডাউনলোড করতে সরাসরি লিঙ্কটি পেস্ট করুন।", reply_markup=markup)

# ---------------- CONTENT SENDING (Original) ----------------
def send_content(chat_id, contents, page=0, category=None):
    per_page = 5
    start_idx = page * per_page
    end_idx = start_idx + per_page
    items = contents[start_idx:end_idx]

    if not items:
        bot.send_message(chat_id, "❌ আর কোনো কন্টেন্ট নেই।")
        return

    for item in items:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("▶ Watch", url=item['link']),
            types.InlineKeyboardButton("⬇ Download", url=item['link'])
        )
        caption = f"🎬 <b>{item['name']}</b>\n📂 {item['category'].upper()}\n⭐ Premium Content"
        try: bot.send_photo(chat_id, item['image'], caption=caption, reply_markup=markup)
        except: bot.send_message(chat_id, f"🎬 {item['name']}\n(Image Error)", reply_markup=markup)

    nav = types.InlineKeyboardMarkup()
    btns = []
    cb_cat = category if category else "all"
    if page > 0: btns.append(types.InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}_{cb_cat}"))
    if end_idx < len(contents): btns.append(types.InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}_{cb_cat}"))
    if btns: nav.add(*btns); bot.send_message(chat_id, f"📄 Page: {page + 1}", reply_markup=nav)

# ---------------- CATEGORY & SEARCH (Original) ----------------
@bot.message_handler(func=lambda m: m.text in ["🎬 Movies", "📺 Dramas", "🎭 Series"])
def category_handler(message):
    cat_map = {"🎬 Movies": "movie", "📺 Dramas": "drama", "🎭 Series": "series"}
    cat = cat_map[message.text]
    contents = list(content_col.find({"category": cat}).sort("_id", -1))
    if not contents: bot.send_message(message.chat.id, "❌ No content found"); return
    send_content(message.chat.id, contents, page=0, category=cat)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def pagination(call):
    data = call.data.split("_")
    page, cat = int(data[1]), data[2]
    contents = list(content_col.find().sort("_id", -1)) if cat == "all" else list(content_col.find({"category": cat}).sort("_id", -1))
    bot.delete_message(call.message.chat.id, call.message.message_id)
    send_content(call.message.chat.id, contents, page, category=cat)

@bot.message_handler(func=lambda m: m.text == "🔍 Search")
def ask_search(message):
    msg = bot.send_message(message.chat.id, "🔍 মুভি বা নাটকের নাম লিখে পাঠান:")
    bot.register_next_step_handler(msg, do_search)

def do_search(message):
    results = list(content_col.find({"name": {"$regex": message.text, "$options": "i"}}))
    if not results: bot.send_message(message.chat.id, "❌ পাওয়া যায়নি!"); return
    send_content(message.chat.id, results, page=0)

# ---------------- ADMIN POST (Original) ----------------
@bot.message_handler(commands=['post'])
def post(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        data = message.text.replace("/post", "").strip().split("|")
        name, cat, image, link = [d.strip() for d in data]
        content_col.insert_one({"name": name, "category": cat.lower(), "image": image, "link": link, "date": time.ctime()})
        bot.send_message(ADMIN_ID, f"✅ Added: {name}")
    except: bot.send_message(ADMIN_ID, "❌ Format: /post name | category | img | link")

# ---------------- RUN ----------------
if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
    
