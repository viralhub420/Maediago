import telebot
import os
import requests
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template
from threading import Thread
from yt_dlp import YoutubeDL
from pymongo import MongoClient

# --- Flask App (Render Ad-Gate) ---
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

def run():
    # Render সাধারণত পোর্ট পরিবেশ ভেরিয়েবল ব্যবহার করে
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Config From Environment Variables ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6311806060))
CH_ID = "@mediago9" 
RENDER_URL = os.environ.get('RENDER_URL') 

bot = telebot.TeleBot(API_TOKEN)

# --- MongoDB Setup ---
try:
    client = MongoClient(MONGO_URI)
    db = client['bot_database']
    users_col = db['users']
except:
    print("MongoDB Connection Error!")

def log_user(user_id):
    try:
        if not users_col.find_one({"user_id": user_id}):
            users_col.insert_one({"user_id": user_id, "join_date": time.ctime()})
    except:
        pass

# --- Force Subscribe Check ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CH_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# --- TikTok Downloader ---
def get_tiktok_video(url):
    try:
        res = requests.get(f"https://api.tiklydown.eu.org/api/download?url={url}", timeout=10).json()
        return res.get('video', {}).get('noWatermark')
    except:
        try:
            res = requests.get(f"https://www.tikwm.com/api/?url={url}", timeout=10).json()
            return res.get('data', {}).get('play')
        except: return None

# --- Commands ---

@bot.message_handler(commands=['start'])
def welcome(message):
    log_user(message.chat.id)
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\n\nযেকোনো ভিডিও লিঙ্ক পাঠান এবং আমাদের চ্যানেল জয়েন করে ডাউনলোড করুন।")

@bot.message_handler(commands=['stats'])
def get_stats(message):
    if message.from_user.id == ADMIN_ID:
        count = users_col.count_documents({})
        bot.send_message(message.chat.id, f"📊 **বোট স্ট্যাটাস:**\n\n👥 মোট ইউজার: {count} জন।")

# --- Link Handler (Force Join + Ad Gate) ---
@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    original_url = message.text # ইউজারের লিঙ্ক এখানে সেভ হলো
    
    # ১. চ্যানেল সাবস্ক্রিপশন চেক
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CH_ID.replace('@', '')}"))
        bot.send_message(message.chat.id, "⚠️ **বোটটি ব্যবহার করতে আগে আমাদের চ্যানেলে জয়েন করুন!**\n\nজয়েন করার পর আবার লিঙ্কটি পাঠান।", reply_markup=markup)
        return

    # ২. জয়েন থাকলে অ্যাড পেজের বাটন দেখাবে (WebApp)
    markup = InlineKeyboardMarkup()
    watch_btn = InlineKeyboardButton(
        text="🎬 Watch Ad to Unlock (SDK)", 
        web_app=WebAppInfo(url=RENDER_URL)
    )
    
    # Callback data-তে ছোট করে লিঙ্ক পাঠানো (টেলিগ্রামের লিমিট থাকে)
    markup.add(watch_btn)
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{int(time.time())}"))

    bot.send_message(message.chat.id, "⚠️ লিঙ্কটি লক করা আছে! \n\nভিডিওটি আনলক করতে উপরের বাটনে ক্লিক করে অন্তত ১ মিনিট অ্যাডটি দেখুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    bot.answer_callback_query(call.id)
    # এখানে লজিক চেক করবে
    sent_time = int(call.data.split('_')[1])
    
    if int(time.time()) - sent_time < 60:
        remaining = 60 - (int(time.time()) - sent_time)
        bot.send_message(call.message.chat.id, f"❌ আপনি এখনো ১ মিনিট দেখেননি! আর {remaining} সেকেন্ড অপেক্ষা করুন।")
    else:
        bot.send_message(call.message.chat.id, "✅ ভেরিফিকেশন সফল! এখন আপনার ভিডিওটি ডাউনলোড হচ্ছে...")
        # এখানে ডাউনলোড লজিক কাজ করবে

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
    
