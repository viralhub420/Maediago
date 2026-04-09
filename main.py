import os
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
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})
    
    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
        markup.add(types.InlineKeyboardButton("🔄 চেক করুন", callback_data="check_join"))
        bot.send_message(user_id, "⚠️ **এক্সেস ডিনাইড!**\n\nচ্যানেলে জয়েন না করলে বোট কাজ করবে না।", reply_markup=markup)
        return
    show_main_menu(user_id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "💰 Earning", "📊 Stats")
    bot.send_message(chat_id, "👋 **MediaGo Hub**-এ স্বাগতম!\n\nভিডিও লিঙ্ক পাঠিয়ে সরাসরি ডাউনলোড করুন অথবা সুপার অ্যাপ ওপেন করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    if is_joined(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো জয়েন করেননি!", show_alert=True)

# --- বটের ভেতর ভিডিও ডাউনলোডার (নিউ ফিচার) ---
@bot.message_handler(func=lambda m: any(x in m.text for x in ["facebook.com", "tiktok.com", "youtube.com", "youtu.be", "instagram.com"]))
def handle_downloader(message):
    video_url = message.text
    direct_ad_link = "https://omg10.com/4/10651831" # আপনার মনিট্যাগ লিঙ্ক
    download_api = f"https://snapsave.app/search?q={video_url}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔓 Unlock Download (Ad)", url=direct_ad_link))
    markup.add(types.InlineKeyboardButton("📥 Download Now", url=download_api))
    
    bot.send_message(message.chat.id, "📥 **ভিডিও লিঙ্ক পাওয়া গেছে!**\n\nপ্রথমে Unlock বাটনে ক্লিক করে অ্যাড দেখুন, তারপর Download বাটনে ক্লিক করুন।", reply_markup=markup)

# --- অ্যাডমিন পোস্ট কমান্ড (ফিক্সড) ---
@bot.message_handler(commands=['post'])
def admin_post(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        raw_text = message.caption if message.caption else message.text
        content_text = raw_text.replace("/post", "").strip()
        data = [x.strip() for x in content_text.split("|")]
        
        if len(data) < 4:
            bot.reply_to(message, "❌ ফরম্যাট: নাম | ক্যাটাগরি | ইমেজ লিঙ্ক | ভিডিও লিঙ্ক")
            return

        name, cat, img, link = data
        content_col.insert_one({"name": name, "category": cat.lower(), "image": img, "link": link})
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Watch / Download", url=f"https://t.me/{bot.get_me().username}?start=search"))
        for ch in POST_CHANNELS:
            try: bot.send_photo(ch, img, caption=f"🎬 <b>New: {name}</b>\n📂 Category: {cat.upper()}", reply_markup=markup)
            except: pass
        bot.reply_to(message, "✅ পোস্ট সফল হয়েছে!")
    except Exception as e:
        bot.reply_to(message, f"❌ ভুল: {str(e)}")

# --- স্ট্যাটাস চেক ---
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID: return
    total = users_col.count_documents({})
    bot.reply_to(message, f"📊 **বোট স্ট্যাটাস**\n\n📱 মোট ইউজার: {total}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
