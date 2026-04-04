import os
import time
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread

# --- কনফিগুরেশন ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNELS = [
    {"id": "@TheDubbedStationBD", "link": "https://t.me/TheDubbedStationBD", "name": "Main Channel"},
]
POST_CHANNELS = ["@TheDubbedStationBD"]

app = Flask(__name__)

# ডাটাবেস কানেকশন
client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), parse_mode="HTML")

# --- ফ্রন্টএন্ড রুট ---
@app.route('/')
def home():
    # ডাটাবেস থেকে সব মুভি/নাটক নিয়ে আসা (লেটেস্টগুলো আগে দেখাবে)
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))))
    t.daemon = True
    t.start()

# --- ফোর্স জয়েন চেক ---
def is_joined(user_id):
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            if status not in ['member', 'administrator', 'creator']: return False
        except: continue
    return True

# --- কমান্ড হ্যান্ডলার ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    # ইউজার সেভ করা
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})
    
    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
        markup.add(types.InlineKeyboardButton("🔄 চেক করুন", callback_data="check_join"))
        bot.send_message(user_id, "⚠️ **এক্সেস ডিনাইড!**\n\nআমাদের চ্যানেলে জয়েন না করলে বোটটি কাজ করবে না।", reply_markup=markup)
        return
    
    show_main_menu(user_id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # সুপার অ্যাপ বাটন
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "💰 Earning", "📊 Stats")
    bot.send_message(chat_id, "👋 **MediaGo Hub**-এ স্বাগতম!\n\nনিচের বাটন থেকে সুপার অ্যাপ ওপেন করুন অথবা যেকোনো ভিডিও লিঙ্ক পাঠিয়ে ডাউনলোড করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if is_joined(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো জয়েন করেননি!", show_alert=True)

# --- ভিডিও ডাউনলোডার রিডাইরেক্ট ---
@bot.message_handler(func=lambda m: any(x in m.text for x in ["facebook.com", "tiktok.com", "youtube.com", "youtu.be", "instagram.com"]))
def handle_downloader(message):
    mini_app_url = f"{os.getenv('RENDER_URL')}?download_url={message.text}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔓 Unlock & Download", web_app=types.WebAppInfo(url=mini_app_url)))
    bot.send_message(message.chat.id, "📥 **ভিডিও লিঙ্ক পাওয়া গেছে!**\n\nনিচের বাটনে ক্লিক করে অ্যাড দেখে আনলক করুন।", reply_markup=markup)

# --- অ্যাডমিন পোস্ট কমান্ড ---
@bot.message_handler(commands=['post'])
def admin_post(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        # ফরম্যাট: /post Name | Category | Image_URL | Video_URL
        data = [x.strip() for x in message.text.replace("/post", "").split("|")]
        name, cat, img, link = data
        
        # ডাটাবেসে সেভ
        content_col.insert_one({"name": name, "category": cat.lower(), "image": img, "link": link})
        
        # চ্যানেলে পোস্ট
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Watch / Download", url=f"https://t.me/{bot.get_me().username}?start=search"))
        for ch in POST_CHANNELS:
            bot.send_photo(ch, img, caption=f"🎬 <b>New Content: {name}</b>\n📂 Category: {cat.upper()}", reply_markup=markup)
            
        bot.send_message(ADMIN_ID, "✅ পোস্ট সফল হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "❌ ভুল ফরম্যাট! সঠিক: /post Name | Category | Img | Link")

# --- ইউজার স্ট্যাটাস ও ক্লিনআপ ---
@bot.message_handler(commands=['stats'])
def stats_cleanup(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(ADMIN_ID, "🔍 ইউজার ডাটাবেস চেক করা হচ্ছে...")
    total = users_col.count_documents({})
    active, deleted = 0, 0
    for user in users_col.find():
        try:
            bot.send_chat_action(user["user_id"], 'typing')
            active += 1
        except:
            users_col.delete_one({"user_id": user["user_id"]})
            deleted += 1
    bot.edit_message_text(f"📊 **স্ট্যাটাস রিপোর্ট**\n\n✅ অ্যাক্টিভ: {active}\n🗑️ ইনঅ্যাক্টিভ ডিলিট: {deleted}\n📱 মোট: {total}", ADMIN_ID, msg.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
