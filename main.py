import telebot
import os
import time
from telebot import types
from telebot.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, render_template
from threading import Thread
from pymongo import MongoClient

# --- Flask & Database Setup ---
app = Flask(__name__)

# MongoDB কানেকশন
MONGO_URI = os.environ.get('MONGO_URI')
client = MongoClient(MONGO_URI)
db = client['mediago_db']
users_col = db['users']
content_col = db['contents']

@app.route('/')
def home():
    # ডাটাবেস থেকে সব কন্টেন্ট নিয়ে এসে মিনি অ্যাপে পাঠানো
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def run():
    # রেন্ডার পোর্টের জন্য এটি জরুরি
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# --- Telegram Bot Setup ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6311806060))
RENDER_URL = os.environ.get('RENDER_URL')
bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def welcome(message):
    # ইউজার ডাটাবেসে সেভ করা
    if not users_col.find_one({"user_id": message.chat.id}):
        users_col.insert_one({"user_id": message.chat.id, "date": time.ctime()})
    
    # কিবোর্ড বাটন (আপনার চাহিদা অনুযায়ী)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_app = KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=WebAppInfo(url=RENDER_URL))
    btn_movie = KeyboardButton("🎬 মুভি ফাইল", web_app=WebAppInfo(url=f"{RENDER_URL}?cat=movie"))
    btn_drama = KeyboardButton("🎭 নাটক ফাইল", web_app=WebAppInfo(url=f"{RENDER_URL}?cat=drama"))
    btn_serial = KeyboardButton("📺 সিরিয়াল ফাইল", web_app=WebAppInfo(url=f"{RENDER_URL}?cat=serial"))
    btn_scanner = KeyboardButton("🔍 ফ্রি স্ক্যানার (No Ads)", web_app=WebAppInfo(url=f"{RENDER_URL}?tool=scanner"))
    btn_down = KeyboardButton("📥 ভিডিও ডাউনলোডার")

    markup.add(btn_app)
    markup.add(btn_movie, btn_drama)
    markup.add(btn_serial, btn_scanner)
    markup.add(btn_down)

    bot.send_message(message.chat.id, "👋 MediaGo Hub-এ স্বাগতম!\nনিচের বাটন থেকে আপনার প্রয়োজনীয় ফাইলটি ওপেন করুন।", reply_markup=markup)

@bot.message_handler(commands=['post'])
def post_content(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        # ফরম্যাট: /post নাম | ক্যাটাগরি | ইমেজ লিঙ্ক | ডাউনলোড লিঙ্ক
        data = message.text.replace('/post ', '').split('|')
        content_data = {
            "name": data[0].strip(),
            "category": data[1].strip().lower(),
            "image": data[2].strip(),
            "link": data[3].strip()
        }
        content_col.insert_one(content_data)
        bot.send_message(ADMIN_ID, f"✅ সফলভাবে {data[1]} সেকশনে পোস্ট হয়েছে!")
    except:
        bot.send_message(ADMIN_ID, "❌ ভুল ফরম্যাট! সঠিক নিয়ম:\n/post নাম | ক্যাটাগরি | ইমেজ লিঙ্ক | লিঙ্ক")

@bot.message_handler(func=lambda m: m.text == "📥 ভিডিও ডাউনলোডার")
def down_info(message):
    bot.send_message(message.chat.id, "🔗 ভিডিও লিঙ্কটি এখানে দিন, আমি ডাউনলোড করে দিচ্ছি!")

if __name__ == "__main__":
    # Flask এবং Bot একসাথে চালানোর জন্য থ্রেডিং
    t = Thread(target=run)
    t.daemon = True
    t.start()
    bot.polling(none_stop=True)
