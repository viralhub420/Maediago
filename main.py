import os
import time
import telebot
from telebot import types
from pymongo import MongoClient

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

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
    markup.row("🎬 Movies", "📺 Dramas")
    markup.row("🎭 Series", "🔍 Search")

    bot.send_message(
        message.chat.id,
        "👋 Welcome to Premium Bot\n\nSelect category or search 🔍",
        reply_markup=markup
    )

# ---------------- CATEGORY ----------------
def send_content(chat_id, contents, page=0):
    per_page = 5
    start = page * per_page
    end = start + per_page

    items = contents[start:end]

    for item in items:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("▶ Watch", url=item['link']),
            types.InlineKeyboardButton("⬇ Download", url=item['link'])
        )

        caption = f"""
🎬 <b>{item['name']}</b>
📂 {item['category']}
⭐ Premium Content
        """

        bot.send_photo(chat_id, item['image'], caption=caption, reply_markup=markup)

    # Pagination
    nav = types.InlineKeyboardMarkup()
    nav.add(
        types.InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"),
        types.InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}")
    )
    bot.send_message(chat_id, "📄 Pages:", reply_markup=nav)

# ---------------- CATEGORY HANDLER ----------------
@bot.message_handler(func=lambda m: m.text in ["🎬 Movies", "📺 Dramas", "🎭 Series"])
def category(message):
    category_map = {
        "🎬 Movies": "movie",
        "📺 Dramas": "drama",
        "🎭 Series": "series"
    }

    cat = category_map[message.text]
    contents = list(content_col.find({"category": cat}).sort("_id", -1))

    if not contents:
        bot.send_message(message.chat.id, "❌ No content found")
        return

    send_content(message.chat.id, contents, page=0)

# ---------------- PAGINATION ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def pagination(call):
    page = int(call.data.split("_")[1])

    contents = list(content_col.find().sort("_id", -1))
    send_content(call.message.chat.id, contents, page)

# ---------------- SEARCH ----------------
@bot.message_handler(func=lambda m: m.text == "🔍 Search")
def ask_search(message):
    msg = bot.send_message(message.chat.id, "🔍 Send movie name:")
    bot.register_next_step_handler(msg, do_search)

def do_search(message):
    query = message.text

    results = list(content_col.find({
        "name": {"$regex": query, "$options": "i"}
    }))

    if not results:
        bot.send_message(message.chat.id, "❌ Not found")
        return

    send_content(message.chat.id, results, page=0)

# ---------------- POST ----------------
@bot.message_handler(commands=['post'])
def post(message):
    if not is_admin(message.from_user.id):
        return

    try:
        data = message.text.replace("/post", "").split("|")

        name = data[0].strip()
        category = data[1].strip().lower()
        image = data[2].strip()
        link = data[3].strip()

        content_col.insert_one({
            "name": name,
            "category": category,
            "image": image,
            "link": link,
            "date": time.ctime()
        })

        bot.send_message(ADMIN_ID, f"✅ Added: {name}")

        # 🔔 Auto Notify
        users = users_col.find()
        for user in users:
            try:
                bot.send_message(user["user_id"], f"🔥 New Added: {name}")
            except:
                pass

    except:
        bot.send_message(ADMIN_ID, "❌ Format:\n/post name | movie | img | link")

# ---------------- RUN ----------------
print("🚀 Premium Bot Running...")
bot.infinity_polling()
