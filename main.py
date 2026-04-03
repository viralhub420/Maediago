import os
import time
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread

# --- মিনি অ্যাপ সাপোর্ট ---
app = Flask(__name__)

# ডাটাবেস কানেকশন
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

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# ---------------- HELPER ----------------
def is_admin(user_id):
    return user_id == ADMIN_ID

def register_user(user_id):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})

# ---------------- START ----------------
@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # সুপার অ্যাপ বাটন (আপনার রেন্ডার ইউআরএল ব্যবহার করে)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "📺 Dramas")
    markup.row("🎭 Series", "🔍 Search")

    bot.send_message(
        message.chat.id,
        "👋 Welcome to MediaGo Hub\n\nSelect category or search 🔍",
        reply_markup=markup
    )

# ---------------- CONTENT SENDING ----------------
def send_content(chat_id, contents, page=0, category=None):
    per_page = 5
    start_idx = page * per_page
    end_idx = start_idx + per_page
    items = contents[start_idx:end_idx]

    if not items:
        bot.send_message(chat_id, "❌ No more content found.")
        return

    for item in items:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("▶ Watch", url=item['link']),
            types.InlineKeyboardButton("⬇ Download", url=item['link'])
        )
        caption = f"🎬 <b>{item['name']}</b>\n📂 {item['category'].upper()}\n⭐ Premium Content"
        try:
            bot.send_photo(chat_id, item['image'], caption=caption, reply_markup=markup)
        except:
            bot.send_message(chat_id, f"🎬 {item['name']}\n(Image Error)", reply_markup=markup)

    # পেজিনেশন লজিক ঠিক করা হয়েছে (ক্যাটাগরি মনে রাখবে)
    nav = types.InlineKeyboardMarkup()
    btns = []
    cb_cat = category if category else "all"
    if page > 0:
        btns.append(types.InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}_{cb_cat}"))
    if end_idx < len(contents):
        btns.append(types.InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}_{cb_cat}"))
    
    if btns:
        nav.add(*btns)
        bot.send_message(chat_id, f"📄 Page: {page + 1}", reply_markup=nav)

# ---------------- HANDLERS ----------------
@bot.message_handler(func=lambda m: m.text in ["🎬 Movies", "📺 Dramas", "🎭 Series"])
def category_handler(message):
    category_map = {"🎬 Movies": "movie", "📺 Dramas": "drama", "🎭 Series": "series"}
    cat = category_map[message.text]
    contents = list(content_col.find({"category": cat}).sort("_id", -1))
    if not contents:
        bot.send_message(message.chat.id, "❌ No content found")
        return
    send_content(message.chat.id, contents, page=0, category=cat)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def pagination(call):
    data = call.data.split("_")
    page = int(data[1])
    cat = data[2]
    
    if cat == "all":
        contents = list(content_col.find().sort("_id", -1))
    else:
        contents = list(content_col.find({"category": cat}).sort("_id", -1))
        
    bot.delete_message(call.message.chat.id, call.message.message_id)
    send_content(call.message.chat.id, contents, page, category=cat)

@bot.message_handler(func=lambda m: m.text == "🔍 Search")
def ask_search(message):
    msg = bot.send_message(message.chat.id, "🔍 Send movie name:")
    bot.register_next_step_handler(msg, do_search)

def do_search(message):
    query = message.text
    results = list(content_col.find({"name": {"$regex": query, "$options": "i"}}))
    if not results:
        bot.send_message(message.chat.id, "❌ Not found")
        return
    send_content(message.chat.id, results, page=0)

# ---------------- POST ----------------
@bot.message_handler(commands=['post'])
def post(message):
    if not is_admin(message.from_user.id): return
    try:
        # Format: /post Name | Category | Img_Link | Watch_Link
        data = message.text.replace("/post", "").strip().split("|")
        name, cat, image, link = [d.strip() for d in data]
        content_col.insert_one({"name": name, "category": cat.lower(), "image": image, "link": link, "date": time.ctime()})
        bot.send_message(ADMIN_ID, f"✅ Added: {name}")
    except:
        bot.send_message(ADMIN_ID, "❌ Format: /post name | category | img | link")

# ---------------- RUN ----------------
if __name__ == "__main__":
    keep_alive()
    print("🚀 Premium Bot Running...")
    bot.infinity_polling()
