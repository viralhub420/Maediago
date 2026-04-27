import os
import time
import requests
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask, render_template
from threading import Thread
from yt_dlp import YoutubeDL

# --- CONFIG ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "6311806060"))
CHANNELS = [{"id": "@TheDubbedStationBD", "link": "https://t.me/TheDubbedStationBD", "name": "Main Channel"}]
POST_CHANNELS = ["@TheDubbedStationBD"]
MONETAG_LINK = "https://omg10.com/4/10651831"

bot = telebot.TeleBot(os.getenv("TELEGRAM_BOT_TOKEN"), parse_mode="HTML")
client = MongoClient(os.getenv("MONGO_URI"))
db = client["super_bot_db"]
users_col = db["users"]
content_col = db["contents"]

app = Flask(__name__)

@app.route('/')
def home():
    all_content = list(content_col.find().sort("_id", -1))
    return render_template('index.html', contents=all_content)

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

def is_joined(user_id):
    for ch in CHANNELS:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            if status not in ['member', 'administrator', 'creator']: return False
        except: return False
    return True

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if not is_joined(user_id):
        markup = types.InlineKeyboardMarkup()
        for ch in CHANNELS: markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link']))
        bot.send_message(user_id, "⚠️ চ্যানেলে জয়েন না করলে বট কাজ করবে না!", reply_markup=markup)
        return
    show_main_menu(user_id)

def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 ওপেন সুপার অ্যাপ", web_app=types.WebAppInfo(url=os.getenv("RENDER_URL"))))
    markup.row("🎬 Movies", "💰 Earning", "📊 Stats")
    bot.send_message(chat_id, "👋 MediaGo Hub-এ স্বাগতম!\nলিঙ্ক পাঠান অথবা অ্যাপ ওপেন করুন।", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text and any(x in m.text for x in ["facebook.com","tiktok.com","youtube.com","youtu.be","instagram.com"]))
def handle_downloader(message):
    users_col.update_one({"user_id": message.chat.id}, {"$set": {"last_url": message.text, "time": int(time.time()), "clicked_ad": False}}, upsert=True)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎬 Watch Ad (1 Min)", callback_data="click_ad_logic"))
    markup.add(types.InlineKeyboardButton("🔓 Unlock Now", callback_data="unlock_video"))
    bot.send_message(message.chat.id, "⚠️ লিঙ্ক লক করা! অ্যাড দেখে আনলক করুন।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "click_ad_logic")
def click_ad_logic(call):
    users_col.update_one({"user_id": call.from_user.id}, {"$set": {"clicked_ad": True}})
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Go to Ad", url=MONETAG_LINK))
    markup.add(types.InlineKeyboardButton("🔓 Unlock Now", callback_data="unlock_video"))
    bot.edit_message_text("⏳ অ্যাড দেখুন... ১ মিনিট পর আনলক বাটন চাপুন।", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "unlock_video")
def unlock_video(call):
    user = users_col.find_one({"user_id": call.from_user.id})
    if not user or not user.get("clicked_ad"):
        bot.answer_callback_query(call.id, "❌ আগে অ্যাড দেখুন!", show_alert=True)
        return

    # সাইজ চেকিং লজিক
    try:
        ydl_opts = {'quiet': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(user["last_url"], download=False)
            filesize = info.get('filesize', 0) or info.get('filesize_approx', 0)
            
            # ৫০ এমবি লিমিট
            if filesize > 50 * 1024 * 1024:
                bot.edit_message_text("❌ **ভিডিওটি অনেক বড়!**\nদয়া করে মিনি অ্যাপের 'Pro Downloader' ফিচারটি ব্যবহার করুন।", call.message.chat.id, call.message.message_id)
                return
    except: pass
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📥 Download Now", callback_data="download_video"))
    bot.edit_message_text("✅ আনলক সফল! এখন ডাউনলোড করুন।", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "download_video")
def download_video(call):
    user = users_col.find_one({"user_id": call.from_user.id})
    url = user["last_url"]
    status_msg = bot.send_message(call.message.chat.id, "⏳ ডাউনলোড হচ্ছে...")
    try:
        file_path = f"vid_{call.from_user.id}.mp4"
        with YoutubeDL({'format': 'best', 'outtmpl': file_path, 'quiet': True}) as ydl: ydl.download([url])
        with open(file_path, 'rb') as video: bot.send_video(call.message.chat.id, video, caption="✅ প্রস্তুত!")
        if os.path.exists(file_path): os.remove(file_path)
        bot.delete_message(call.message.chat.id, status_msg.message_id)
    except: bot.send_message(call.message.chat.id, "❌ ডাউনলোড এরর!")

@bot.message_handler(commands=['post', 'stats'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    if message.text.startswith('/stats'):
        total = users_col.count_documents({})
        bot.reply_to(message, f"📊 Total Users: {total}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
                                         
