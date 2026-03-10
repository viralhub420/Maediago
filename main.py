import telebot
import os
import requests
import time
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template
from threading import Thread
from yt_dlp import YoutubeDL
from pymongo import MongoClient

# --- Flask App ---
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Config ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
MONGO_URI = os.environ.get('MONGO_URI') 
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6311806060))
CH_ID = "@mediago9" 
RENDER_URL = os.environ.get('RENDER_URL') 

bot = telebot.TeleBot(API_TOKEN)

# --- MongoDB ---
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
    # মিনি অ্যাপ মেনু বাটন
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    app_btn = types.KeyboardButton("🚀 Open Mini App", web_app=WebAppInfo(url=RENDER_URL))
    markup.add(app_btn)
    bot.send_message(message.chat.id, "👋 **স্বাগতম!**\n\nভিডিওর লিঙ্ক পাঠান অথবা আমাদের অ্যাপ ব্যবহার করুন।", reply_markup=markup)

# --- Link Handler ---
# আমরা একটি ডিকশনারি ব্যবহার করব লিঙ্কগুলো সাময়িকভাবে মনে রাখার জন্য
pending_links = {}

@bot.message_handler(func=lambda message: "http" in message.text)
def handle_link(message):
    log_user(message.chat.id)
    original_url = message.text
    
    if not is_subscribed(message.chat.id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CH_ID.replace('@', '')}"))
        bot.send_message(message.chat.id, "⚠️ **বোটটি ব্যবহার করতে আগে আমাদের চ্যানেলে জয়েন করুন!**", reply_markup=markup)
        return

    # লিঙ্কটি সেভ করে রাখা হচ্ছে যাতে Unlock বাটনে ক্লিক করলে পাওয়া যায়
    pending_links[message.chat.id] = original_url
    
    markup = InlineKeyboardMarkup()
    watch_btn = InlineKeyboardButton(text="🎬 Watch Ad to Unlock (SDK)", web_app=WebAppInfo(url=RENDER_URL))
    unlock_btn = InlineKeyboardButton("🔓 Unlock Now", callback_data=f"unl_{int(time.time())}")
    markup.add(watch_btn)
    markup.add(unlock_btn)

    bot.send_message(message.chat.id, "⚠️ লিঙ্কটি লক করা আছে! \n\nনিচের বাটনে ক্লিক করে অন্তত ১ মিনিট অ্যাডটি দেখুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unl_'))
def process_unlock(call):
    bot.answer_callback_query(call.id)
    sent_time = int(call.data.split('_')[1])
    user_id = call.message.chat.id
    
    if int(time.time()) - sent_time < 60:
        remaining = 60 - (int(time.time()) - sent_time)
        bot.send_message(user_id, f"❌ আপনি এখনো ১ মিনিট দেখেননি! আর {remaining} সেকেন্ড অপেক্ষা করুন।")
    else:
        # লিঙ্কটি খুঁজে বের করা
        url = pending_links.get(user_id)
        if not url:
            bot.send_message(user_id, "❌ কোনো লিঙ্ক পাওয়া যায়নি। আবার লিঙ্কটি পাঠান।")
            return

        status_msg = bot.send_message(user_id, "⏳ ভেরিফিকেশন সফল! ভিডিওটি প্রস্তুত হচ্ছে...")
        
        try:
            if "tiktok.com" in url:
                video_link = get_tiktok_video(url)
                if video_link:
                    bot.send_video(user_id, video_link, caption="✅ TikTok ডাউনলোড সম্পন্ন!")
                else:
                    bot.send_message(user_id, "❌ TikTok ভিডিওটি পাওয়া যায়নি।")
            else:
                # FB, YouTube, etc using yt-dlp
                file_path = f"vid_{user_id}.mp4"
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'outtmpl': file_path,
                    'max_filesize': 50 * 1024 * 1024, # Render মেমরি সেফটি
                    'quiet': True
                }
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                with open(file_path, 'rb') as video:
                    bot.send_video(user_id, video, caption="✅ ভিডিও ডাউনলোড সম্পন্ন!")
                
                if os.path.exists(file_path): os.remove(file_path)
            
            bot.delete_message(user_id, status_msg.message_id)
            del pending_links[user_id] # কাজ শেষ হলে ডিকশনারি থেকে মুছে ফেলা
        except Exception as e:
            bot.send_message(user_id, "❌ ডাউনলোড এরর! ভিডিওটি বড় হতে পারে অথবা লিঙ্কটি সঠিক নয়।")
            if user_id in pending_links: del pending_links[user_id]

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
        
