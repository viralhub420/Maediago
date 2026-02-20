import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
import os

# আপনার তথ্যগুলো এখানে দিন
API_TOKEN = '8588969365:AAGM5j4hBO11fN_rSsCU9JKErCm1OLYN8WE' 
CHANNEL_ID = '@mediago9' 
MONETAG_LINK = 'https://omg10.com/4/10453524'

bot = telebot.TeleBot(API_TOKEN)

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 MediaGoBot-এ স্বাগতম!\nলিঙ্ক পাঠান, আমি ভিডিও দিচ্ছি।")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    url = message.text
    if "http" in url:
        if not is_subscribed(user_id):
            markup = InlineKeyboardMarkup()
            btn = InlineKeyboardButton("📢 জয়েন করুন", url=f"https://t.me/{CHANNEL_ID[1:]}")
            markup.add(btn)
            bot.send_message(message.chat.id, "❌ আগে আমাদের চ্যানেলে জয়েন করুন!", reply_markup=markup)
            return

        markup = InlineKeyboardMarkup()
        ad_btn = InlineKeyboardButton("📥 আনলক করুন (অ্যাড)", url=MONETAG_LINK)
        confirm_btn = InlineKeyboardButton("✅ ডাউনলোড শুরু করুন", callback_data=f"dl_{url}")
        markup.add(ad_btn, confirm_btn)
        bot.send_message(message.chat.id, "ভিডিওটি প্রস্তুত। আনলক করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_"))
def process_download(call):
    video_url = call.data.replace("dl_", "")
    bot.edit_message_text("⏳ ডাউনলোড হচ্ছে...", call.message.chat.id, call.message.message_id)
    ydl_opts = {'format': 'best', 'outtmpl': 'video.mp4', 'quiet': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        with open('video.mp4', 'rb') as video:
            bot.send_video(call.message.chat.id, video, caption="✅ MediaGoBot Success!")
        os.remove('video.mp4')
    except:
        bot.send_message(call.message.chat.id, "❌ সমস্যা হয়েছে, আবার চেষ্টা করুন।")

# Hugging Face-এর জন্য non_stop=True ব্যবহার করা জরুরি
bot.polling(non_stop=True)
                                                                   
