import os
import json
import requests
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types

# الإعدادات
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))
CHANNEL_ID = -1004420116275 

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)  # ضروري لـ Vercel

@app.route('/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

@bot.message_handler(func=lambda message: True)
def handle_report(message):
    if message.text.startswith('/'): return
    
    # 1. استخراج الحقول من النص
    text = message.text
    lines = text.split('\n')
    def get_field(field_name):
        for line in lines:
            if line.strip().startswith(field_name):
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
        'عدد الفتية': get_field('عدد الفتية'),
        'وقت التسجيل': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # 2. إضافة اسم المرسل
    sender = message.from_user
    sender_info = f"{sender.first_name} {sender.last_name or ''}".strip()
    if sender.username: sender_info += f" (@{sender.username})"
    data['اسم المرسل'] = sender_info

    # 3. محاولة الحفظ والإرسال
    try:
        requests.post(GOOGLE_SHEET_URL, json=data, timeout=15)
        
        # صياغة التقرير الكامل للقناة
        notification = (
            f"🔔 *تقرير جديد*\n"
            f"👤 المُرسِل: {sender_info}\n"
            f"🕐 الوقت: {data['وقت التسجيل']}\n\n"
            f"🗺️ المحافظة: {data['المحافظة']}\n"
            f"📍 المنطقة: {data['المنطقة']}\n"
            f"📅 التاريخ: {data['التاريخ']}\n"
            f"🏕️ اسم الفرقة: {data['اسم الفرقة']}\n"
            f"👥 الفئة: {data['الفئة']}\n"
            f"⚡ نوع النشاط: {data['نوع النشاط']}\n"
            f"📝 اسم النشاط: {data['اسم النشاط']}\n"
            f"👨‍✈️ اسم القائد: {data['اسم القائد']}\n"
            f"🤝 مساعد القائد: {data['اسم مساعد القائد'] or '—'}\n"
            f"🧒 عدد الفتية: {data['عدد الفتية']}"
        )
        
        bot.send_message(CHANNEL_ID, notification, parse_mode='Markdown')
        bot.reply_to(message, "✅ تم استلام البيانات وحفظها في Google Sheets وإرسالها للقناة بنجاح!")
        
    except Exception as e:
        bot.reply_to(message, f"❌ فشل الحفظ أو الإرسال: {str(e)}")

if __name__ == '__main__':
    app.run()
