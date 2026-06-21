import os
import json
import threading
import requests
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

GOOGLE_SHEET_URL = os.environ.get(
    'GOOGLE_SHEET_URL',
    'https://script.google.com/macros/s/AKfycbxcIAdUYH-GMwdk8DKerK1AkHkgvk8LQNbhCQttYlAXBTCema-tBlXko31XLWDgX6jJ/exec'
)
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))
CHANNEL_ID = -1004420116275 
STATS_FILE = '/tmp/stats.json'

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__) 

@app.route('/')
def index():
    return 'Bot Server is Running!', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Invalid Content-Type', 403

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {'total': 0, 'by_province': {}, 'by_activity': {}}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return {'total': 0, 'by_province': {}, 'by_activity': {}}

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

@bot.message_handler(func=lambda message: True)
def handle_report(message):
    text = message.text
    lines = text.split('\n')

    def get_field(field_name):
        for line in lines:
            if line.strip().startswith(field_name):
                for sep in (':', '：'):
                    parts = line.split(sep, 1)
                    if len(parts) > 1: return parts[1].strip()
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

    # القائمة الإجبارية (تم إضافة اسم مساعد القائد لها)
    required = [
        'المحافظة', 'المنطقة', 'التاريخ', 'اسم الفرقة', 'الفئة', 
        'نوع النشاط', 'اسم النشاط', 'اسم القائد', 'اسم مساعد القائد', 'عدد الفتية'
    ]
    missing = [f for f in required if not data[f]]
    
    if missing:
        bot.reply_to(message, f"⚠️ عذراً، لم يتم حفظ التقرير لأنك تركت هذه الحقول فارغة:\n❌ ({', '.join(missing)})")
        return

    payload = {
        'date': data['التاريخ'],
        'governorate': data['المحافظة'],
        'region': data['المنطقة'],
        'team_name': data['اسم الفرقة'],
        'category': data['الفئة'],
        'activity_type': data['نوع النشاط'],
        'activity_name': data['اسم النشاط'],
        'leader_name': data['اسم القائد'],
        'assistant_name': data['اسم مساعد القائد'],
        'members_count': data['عدد الفتية'],
        'timestamp': data['وقت التسجيل'],
    }

    try:
        response = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=15)
        if response.status_code != 200:
            bot.reply_to(message, "❌ فشل الحفظ في Google Sheets.")
            return

        update_stats(data)
        bot.reply_to(message, "✅ تم استلام البيانات وحفظها بنجاح!")

        sender = message.from_user
        sender_info = f"@{sender.username}" if sender.username else f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        stats = load_stats()
        notification = (
            f"🔔 *تقرير جديد* — #{stats['total']}\n👤 المُرسِل: {sender_info}\n\n"
            f"🗺️ المحافظة: {data['المحافظة']}\n📍 المنطقة: {data['المنطقة']}\n📅 التاريخ: {data['التاريخ']}\n"
            f"🏕️ اسم الفرقة: {data['اسم الفرقة']}\n👥 الفئة: {data['الفئة']}\n⚡ نوع النشاط: {data['نوع النشاط']}\n"
            f"📝 اسم النشاط: {data['اسم النشاط']}\n👨‍✈️ اسم القائد: {data['اسم القائد']}\n🤝 مساعد القائد: {data['اسم مساعد القائد']}\n🧒 عدد الفتية: {data['عدد الفتية']}'sender': sender_info  # <--- إضافة هذه السطر"
        )
        try:
            bot.send_message(CHANNEL_ID, notification, parse_mode='Markdown')
        except:
            pass

    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
