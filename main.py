import os
import time
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread

# --- কনফিগ ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNELS = [
    {"id": "@TheDubbedStationBD", "link": "https://t.me/TheDubbedStationBD", "name": "Main Channel"},
    {"id": "@mediastationbd", "link": "https://t.me/mediastationbd", "name": "Backup Channel"},
]
POST_CHANNELS = ["@TheDubbedStationBD"] # যেসব চ্যানেলে অটো পোস্ট যাবে

app = Flask(__name__)
client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), parse_mode="HTML")

@app.route('/')
def home():
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def keep_alive():
    t = Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000))))
    t.daemon = True
    t.start()

# --- ফোর্স জয়েন চেক ---
def get_not_joined(user_id):
    not_joined = []
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            if status not in ['member', 'administrator', 'creator']: not_joined.append(ch)
        except: continue
    return not_joined

# --- স্টার্ট কমান্ড ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not users_col.find_one({"user_id": user_id}): 
        users_col.insert_one({"user_id": user_id})
    
    not_joined = get_not_joined(user_id)
    if not_joined:
        markup = types.InlineKeyboardMarkup()
        for ch in not_joined: markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
        markup.add(types.InlineKeyboardButton("🔄 চেক করুন (Check Join)", callback_data="check_status"))
        bot.send_message(user_id, "⚠️ **এক্সেস ডিনাইড!**\nবোটের সার্ভিসগুলো ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=markup)
        return
    show_menu(user_id)

def show_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "📺 Dramas", "🎭 Series")
    markup.row("🔍 Search")
    bot.send_message(chat_id, "👋 **MediaGo Hub**-এ স্বাগতম!\nভিডিও ডাউনলোড করতে লিঙ্কটি পেস্ট করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_status")
def check_status(call):
    if not get_not_joined(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_menu(call.message.chat.id)
    else: bot.answer_callback_query(call.id, "❌ আপনি এখনো জয়েন করেননি!", show_alert=True)

# --- ডাউনলোডার লজিক (মিনি অ্যাপে রিডাইরেক্ট) ---
@bot.message_handler(func=lambda m: any(x in m.text for x in ["facebook.com", "tiktok.com", "youtube.com", "youtu.be", "instagram.com"]))
def handle_link(message):
    mini_app_url = f"{os.getenv('RENDER_URL')}?download_url={message.text}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔓 Unlock & Download Video", web_app=types.WebAppInfo(url=mini_app_url)))
    bot.send_message(message.chat.id, "📥 **ভিডিওটি প্রস্তুত!**\nনিচের বাটনে ক্লিক করে আনলক করুন।", reply_markup=markup)

# --- অটো পোস্ট ও ব্রডকাস্ট ---
@bot.message_handler(commands=['post'])
def post_content(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        # ফরম্যাট: /post Name | Category | Img_Link | Watch_Link
        data = message.text.replace("/post", "").strip().split("|")
        name, cat, img, link = [x.strip() for x in data]
        content_col.insert_one({"name": name, "category": cat.lower(), "image": img, "link": link})
        
        # চ্যানেলে অটো পোস্ট
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Watch / Download Now", url=f"https://t.me/{bot.get_me().username}?start=search"))
        post_caption = f"🎬 <b>নতুন কন্টেন্ট আপলোড!</b>\n\n📌 <b>নাম:</b> {name}\n📂 <b>ক্যাটাগরি:</b> {cat.upper()}"
        for ch in POST_CHANNELS:
            try: bot.send_photo(ch, img, caption=post_caption, reply_markup=markup)
            except: pass
            
        # সব ইউজারকে ব্রডকাস্ট করা
        for user in users_col.find():
            try: bot.send_message(user["user_id"], f"🔥 <b>নতুন ভিডিও যোগ হয়েছে:</b> {name}\nবটে চেক করুন!")
            except: pass
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে ডাটাবেস ও চ্যানেলে পোস্ট করা হয়েছে!")
    except: bot.send_message(ADMIN_ID, "❌ ফরম্যাট: /post Name | Category | Img | Link")

# --- অ্যাক্টিভ ইউজার ক্লিনআপ ---
@bot.message_handler(commands=['stats'])
def stats_cleanup(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(ADMIN_ID, "🔍 ইউজার ডাটাবেস স্ক্যান করা হচ্ছে এবং ইনঅ্যাক্টিভ ইউজার ডিলিট করা হচ্ছে...")
    total = users_col.count_documents({})
    active, deleted = 0, 0
    for user in users_col.find():
        try:
            bot.send_chat_action(user["user_id"], 'typing')
            active += 1
        except:
            users_col.delete_one({"user_id": user["user_id"]})
            deleted += 1
        time.sleep(0.05)
    bot.edit_message_text(f"📊 **স্ট্যাটাস রিপোর্ট**\n\n✅ অ্যাক্টিভ: {active}\n🗑️ ডিলিট হয়েছে: {deleted}\n📱 মোট: {total}", ADMIN_ID, msg.message_id)

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
    
