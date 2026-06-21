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
STATS_FILE = '/tmp/stats.json'

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# --- وظائف الإحصائيات ---
def load_stats():
    if not os.path.exists(STATS_FILE): return {'total': 0, 'by_province': {}, 'by_activity': {}}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {'total': 0, 'by_province': {}, 'by_activity': {}}

def save_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def update_stats(data):
    stats = load_stats()
    stats['total'] += 1
    province = data.get('المحافظة', 'غير محدد')
    activity = data.get('نوع النشاط', 'غير محدد')
    stats['by_province'][province] = stats['by_province'].get(province, 0) + 1
    stats['by_activity'][activity] = stats['by_activity'].get(activity, 0) + 1
    save_stats(stats)

# --- أوامر البوت الأساسية ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "أهلاً بك! يرجى نسخ القالب التالي وملئه وإرساله في رسالة واحدة:\n\n"
        "المحافظة:\nالمنطقة:\nالتاريخ:\nاسم الفرقة:\nالفئة:\n"
        "نوع النشاط:\nاسم النشاط:\nاسم القائد:\nاسم مساعد القائد:\nعدد الفتية:"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("إرسال تقرير جديد"))
    bot.reply_to(message, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "إرسال تقرير جديد")
def request_report(message):
    template = ("المحافظة:\nالمنطقة:\nالتاريخ:\nاسم الفرقة:\nالفئة:\nنوع النشاط:\nاسم النشاط:\nاسم القائد:\nاسم مساعد القائد:\nعدد الفتية:")
    bot.reply_to(message, "قم بنسخ النص التالي، املأ الفراغات ثم أرسله:\n\n" + template)

# --- معالجة التقارير ---
@bot.message_handler(func=lambda message: not message.text.startswith('/') and message.text != "إرسال تقرير جديد")
def handle_report(message):
    text = message.text
    lines = text.split('\n')

    def get_field(field_name):
        for line in lines:
            if line.strip().startswith(field_name):
                parts = line.split(':', 1)
                return parts[1].strip() if len(parts) > 1 else ""
        return ""

# استخراج البيانات حسب القالب في الصورة
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
 

    required = ['المحافظة', 'المنطقة', 'التاريخ', 'اسم الفرقة', 'الفئة', 'نوع النشاط', 'اسم النشاط', 'اسم القائد', 'اسم مساعد القائد', 'عدد الفتية']
    missing = [f for f in required if not data[f]]
    
    if missing:
        bot.reply_to(message, f"⚠️ حقول مفقودة يرجى التأكد من ملئها:\n{', '.join(missing)}")
        return

    sender = message.from_user
    sender_info = f"@{sender.username}" if sender.username else f"{sender.first_name} {sender.last_name or ''}".strip()

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
        'وقت التسجيل': data['وقت التسجيل'],
        'اسم المرسل': sender_info
    }

    try:
        response = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=15)
        if response.status_code == 200:
            update_stats(data)
            bot.reply_to(message, "✅ تم استلام البيانات وحفظها بنجاح!")
            try:
                bot.send_message(CHANNEL_ID, f"🔔 تقرير جديد من {sender_info}\n\n" + text)
            except: pass
        else:
            bot.reply_to(message, "❌ فشل الحفظ في Google Sheets.")
    except Exception as e:
        bot.reply_to(message, f"خطأ: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
