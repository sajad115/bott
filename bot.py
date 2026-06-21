import os
import json
import requests
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types

# الإعدادات
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', 'https://script.google.com/macros/s/AKfycbxcIAdUYH-GMwdk8DKerK1AkHkgvk8LQNbhCQttYlAXBTCema-tBlXko31XLWDgX6jJ/exec')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))
CHANNEL_ID = -1004420116275 # معرف قناتك
STATS_FILE = '/tmp/stats.json'

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__) # ضروري لعمل Vercel

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
    return 'Forbidden', 403

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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("إرسال تقرير جديد"))
    bot.reply_to(message, "مرحباً! اضغط الزر أدناه لإرسال التقرير.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "إرسال تقرير جديد")
def request_report(message):
    template = "المحافظة: \nالمنطقة: \nالتاريخ: \nاسم الفرقة: \nالفئة: \nنوع النشاط: \nاسم النشاط: \nاسم القائد: \nاسم مساعد القائد: \nعدد الفتية: "
    bot.reply_to(message, "قم بنسخ هذا القالب وملئه:\n\n" + template)

@bot.message_handler(func=lambda message: True)
def handle_report(message):
    if message.text.startswith('/'): return # تجاهل الأوامر
    
    lines = message.text.split('\n')
    def get_field(field):
        for line in lines:
            if line.strip().startswith(field):
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

    # التحقق من البيانات
    if not all([data['المحافظة'], data['اسم القائد'], data['عدد الفتية']]):
        bot.reply_to(message, "⚠️ يرجى التأكد من ملء الحقول الأساسية.")
        return

    # إرسال للشيت
    try:
        requests.post(GOOGLE_SHEET_URL, json=data, timeout=10)
        update_stats(data)
        bot.reply_to(message, "✅ تم الحفظ بنجاح!")
        
        # إرسال للقناة
       # هذا هو نص التنبيه الكامل كما كنت تريده
        notification = (
            f"🔔 *تقرير جديد* — #{load_stats()['total']}\n\n"
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
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

# لا تحذف هذا السطر، Vercel يحتاج لـ app ليشتغل
if __name__ == '__main__':
    app.run()
