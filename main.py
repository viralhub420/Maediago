import telebot
import os
import requests
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
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
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Config From Environment Variables ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6311806060))
CH_ID = "@mediago9"  # সরাসরি আপনার চ্যানেল ইউজারনেম বসিয়ে দেওয়া হয়েছে
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
        # বোট চেক করবে ইউজার মেম্বার, অ্যাডমিন নাকি ক্রিয়েটর
        status = bot.get_chat_member(CH_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        # যদি ইউজার জয়েন না থাকে বা বোট অ্যাডমিন না হয় তবে False দিবে
        return False

# --- TikTok Downloader (Dual API) ---
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

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id == ADMIN_ID:
        msg_text = message.text.replace('/broadcast ', '')
        if msg_text == '/broadcast' or not msg_text:
            bot.send_message(message.chat.id, "⚠️ ব্যবহার: `/broadcast আপনার মেসেজ`")
            return
        
        users = users_col.find()
        count = 0
        for user in users:
            try:
                bot.send_message(user['user_id'], msg_text)
                count += 1
            except: continue
        bot.send_message(message.chat.id, f"✅ {count} জন ইউজারের কাছে পাঠানো হয়েছে।")

# --- Link Handler (Force Join + Ad Gate) ---
@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    
    # ১. প্রথমে চেক করবে চ্যানেলে জয়েন আছে কিনা
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CH_ID.replace('@', '')}"))
        bot.send_message(message.chat.id, "⚠️ **বোটটি ব্যবহার করতে আগে আমাদের চ্যানেলে জয়েন করুন!**\n\nজয়েন করার পর আবার লিঙ্কটি পাঠান।", reply_markup=markup)
        return

    # ২. জয়েন থাকলে অ্যাড পেজের লিঙ্ক দেখাবে
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎬 Watch Ad to Unlock (SDK)", url=RENDER_URL))
    markup.add(InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{int(time.time())}_{message.text}"))
    
    bot.send_message(message.chat.id, "⚠️ **লিঙ্কটি লক করা আছে!**\n\nভিডিওটি আনলক করতে উপরের বাটনে ক্লিক করে অন্তত ১ মিনিট অ্যাডটি দেখুন।", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    bot.answer_callback_query(call.id)
    data = call.data.split('_')
    sent_time, original_url = int(data[1]), data[2]
    
    if int(time.time()) - sent_time < 60:
        remaining = 60 - (int(time.time()) - sent_time)
        bot.send_message(call.message.chat.id, f"❌ আপনি এখনো ১ মিনিট দেখেননি! আর {remaining} সেকেন্ড অপেক্ষা করুন।")
    else:
        status_msg = bot.send_message(call.message.chat.id, "⏳ প্রসেসিং হচ্ছে...")
        try:
            if "tiktok.com" in original_url:
                video_link = get_tiktok_video(original_url)
                if video_link:
                    bot.send_video(call.message.chat.id, video_link, caption="✅ TikTok প্রস্তুত!")
                else:
                    bot.send_message(call.message.chat.id, "❌ ভিডিও পাওয়া যায়নি।")
            else:
                # FB, YouTube, etc.
                file_path = f"vid_{call.message.chat.id}.mp4"
                ydl_opts = {'format': 'best', 'outtmpl': file_path, 'quiet': True}
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([original_url])
                
                with open(file_path, 'rb') as video:
                    bot.send_video(call.message.chat.id, video, caption="✅ ভিডিও ডাউনলোড সম্পন্ন!")
                
                if os.path.exists(file_path): os.remove(file_path)
            
            bot.delete_message(call.message.chat.id, status_msg.message_id)
        except:
            bot.send_message(call.message.chat.id, "❌ ডাউনলোড এরর! লিঙ্ক চেক করুন।")

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
