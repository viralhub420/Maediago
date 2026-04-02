import telebot
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

