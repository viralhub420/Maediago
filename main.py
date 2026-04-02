import telebot
import os
import time
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from flask import Flask, render_template, request, jsonify
from threading import Thread
from pymongo import MongoClient

# --- Flask App ---
app = Flask(__name__)

# MongoDB কানেকশন (মুভি ও ইউজার ডেটা রাখার জন্য)
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['super_bot_db']
users_col = db['users']
content_col = db['contents'] # এখানে মুভি/নাটক সেভ হবে

@app.route('/')
def home():
    # ডাটাবেস থেকে সব মুভি ও নাটক নিয়ে এসে মিনি অ্যাপে পাঠানো
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- Config ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6311806060))
RENDER_URL = os.environ.get('RENDER_URL')

bot = telebot.TeleBot(API_TOKEN)

# --- Admin Functions ---

# ১. ব্রডকাস্ট সিস্টেম (সব ইউজারকে মেসেজ পাঠানো)
@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    
    msg_text = message.text.replace('/broadcast ', '')
    if not msg_text or msg_text == '/broadcast':
        bot.send_message(ADMIN_ID, "❌ ব্যবহার: `/broadcast আপনার মেসেজ`", parse_mode="Markdown")
        return

    users = users_col.find()
    count = 0
    for user in users:
        try:
            bot.send_message(user['user_id'], msg_text)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"✅ {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে।")

# ২. মুভি/নাটক পোস্ট সিস্টেম
# ফরম্যাট: /post নাম | ক্যাটাগরি | ইমেজ_লিংক | ডাউনলোড_লিংক
@bot.message_handler(commands=['post'])
def post_content(message):
    if message.from_user.id != ADMIN_ID: return
    
    try:
        data = message.text.replace('/post ', '').split('|')
        name = data[0].strip()
        category = data[1].strip() # মুভি বা নাটক
        img = data[2].strip()
        link = data[3].strip()

        content_data = {
            "name": name,
            "category": category,
            "image": img,
            "link": link,
            "date": time.ctime()
        }
        content_col.insert_one(content_data)
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে পোস্ট হয়েছে: {name}\nএটি এখন মিনি অ্যাপে দেখা যাবে।")
        
        # চাইলে পোস্ট করার সাথে সাথে সবাইকে নোটিফিকেশন পাঠাতে পারেন
        # broadcast_new_post(name) 
    except:
        bot.send_message(ADMIN_ID, "❌ ফরম্যাট ভুল! \nব্যবহার: `/post মুভির নাম | মুভি | ইমেজ ইউআরএল | ডাউনলোড লিঙ্ক`", parse_mode="Markdown")

# --- User Commands ---
@bot.message_handler(commands=['start'])
def welcome(message):
    # ইউজার লগ করা
    if not users_col.find_one({"user_id": message.chat.id}):
        users_col.insert_one({"user_id": message.chat.id, "join_date": time.ctime()})
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=WebAppInfo(url=RENDER_URL)))
    
    bot.send_message(message.chat.id, "👋 স্বাগতম! আমাদের অ্যাপে মুভি, নাটক এবং এআই টুলস ব্যবহার করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup)

if __name__ == "__main__":
    keep_alive()
    bot.polling(none_stop=True)
    
