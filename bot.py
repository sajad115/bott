import os
import json
import requests
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types

BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbxcIAdUYH-GMwdk8DKerK1AkHkgvk8LQNbhCQttYlAXBTCema-tBlXko31XLWDgX6jJ/exec')
CHANNEL_ID = -1004420116275
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))
STATS_FILE = '/tmp/stats.json'

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

def load_stats():
    if not os.path.exists(STATS_FILE): return {'reports': []}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {'reports': []}

def save_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = "أهلاً بك! يرجى نسخ القالب التالي وملئه:\n\nالمحافظة:\nالمنطقة:\nالتاريخ:\nاسم الفرقة:\nالفئة:\nنوع النشاط:\nاسم النشاط:\nاسم القائد:\nاسم مساعد القائد:\nعدد الفتية:"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("إرسال تقرير جديد"))
    bot.reply_to(message, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "إرسال تقرير جديد")
def request_report(message):
    template = ("المحافظة:\nالمنطقة:\nالتاريخ:\nاسم الفرقة:\nالفئة:\nنوع النشاط:\nاسم النشاط:\nاسم القائد:\nاسم مساعد القائد:\nعدد الفتية:")
    bot.reply_to(message, "انسخ النص التالي، املأ الفراغات وأرسله:\n\n" + template)

@bot.message_handler(func=lambda message: not message.text.startswith('/') and message.text != "إرسال تقرير جديد")
def handle_report(message):
    lines = message.text.split('\n')
    def get_field(name):
        for line in lines:
            if line.strip().startswith(name):
                parts = line.split(':', 1)
                return parts[1].strip() if len(parts) > 1 else ""
        return ""

    data = {
        'المحافظة': get_field('المحافظة'),
        'المنطقة': get_field('المنطقة'),
        'التاريخ': get_field('التاريخ'),
        'اسم الفرقة': get_field('اسم الفرقة'),
        'الفئة': get_field('الفئة'),
        'نوع النشاط': get_field('نوع النشاط'),
        'اسم النشاط': get_field('اسم النشاط'),
        'اسم القائد': get_field('اسم القائد'),
        'اسم مساعد القائد': get_field('اسم مساعد القائد'),
        'عدد الفتية': get_field('عدد الفتية')
    }

    if any(not val for val in data.values()):
        bot.reply_to(message, "⚠️ عذراً، لم يتم حفظ التقرير لوجود حقول فارغة.")
        return

    sender_info = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    
    payload = {
        'التاريخ': data['التاريخ'], 
        'المحافظة': data['المحافظة'], 
        'المنطقة': data['المنطقة'],
        'اسم الفرقة': data['اسم الفرقة'], 
        'الفئة': data['الفئة'], 
        'نوع النشاط': data['نوع النشاط'],
        'اسم النشاط': data['اسم النشاط'], 
        'اسم القائد': data['اسم القائد'],
        'اسم مساعد القائد': data['اسم مساعد القائد'], 
        'عدد الفتية': data['عدد الفتية'],
        'وقت التسجيل': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'اسم المرسل': sender_info
    }

    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=10)
        bot.reply_to(message, "✅ تم الحفظ بنجاح!")
        # تحديث الإحصائيات... (اختياري)
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الاتصال: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
