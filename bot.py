import os
import telebot
from flask import Flask, request

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)  # هذا هو الـ "app" الذي يبحث عنه Vercel

# دالة استقبال الرسائل من تليجرام
@app.route('/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# دالة التأكد من عمل السيرفر
@app.route('/')
def index():
    return 'Bot is running', 200

# لا تضع bot.polling() هنا، لأن Vercel هو من سيدير التشغيل
