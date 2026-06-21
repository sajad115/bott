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
    if not os.path.exists(STATS_FILE): return {'total': 0, 'reports': []}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {'total': 0, 'reports': []}

def save_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

# 1. أمر التقرير الشامل (يعرض المحافظة والفرقة والعدد)
@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id != ADMIN_ID: return
    stats = load_stats()
    if not stats['reports']:
        bot.reply_to(message, "📊 لا توجد تقارير مسجلة.")
        return
    
    report_text = "📋 *تقرير النشاطات الشامل:*\n\n"
    for r in stats['reports']:
        report_text += f"🗺️ {r['المحافظة']} | 🏕️ {r['الفرقة']} | 🧒 {r['العدد']}\n"
    
    bot.reply_to(message, report_text, parse_mode='Markdown')

# 2. استقبال التقارير (شرط عدم بدء الرسالة بـ / يمنع تداخلها مع الأوامر)
@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_report(message):
    if message.text == "إرسال تقرير جديد": return
    
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
        'الفرقة': get_field('اسم الفرقة'),
        'الفئة': get_field('الفئة'),
        'النشاط': get_field('اسم النشاط'),
        'القائد': get_field('اسم القائد'),
        'المساعد': get_field('اسم مساعد القائد'),
        'العدد': get_field('عدد الفتية')
    }

    # التحقق من الإجبارية
    if any(not val for val in data.values()):
        bot.reply_to(message, "⚠️ عذراً، يرجى ملء كافة حقول القالب.")
        return

    # حفظ في الشيت
    sender_info = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    payload = {
        'التاريخ': data['التاريخ'], 'المحافظة': data['المحافظة'], 'المنطقة': data['المنطقة'],
        'اسم الفرقة': data['الفرقة'], 'الفئة': data['الفئة'], 'نوع النشاط': data['النشاط'],
        'اسم القائد': data['القائد'], 'اسم مساعد القائد': data['المساعد'],
        'عدد الفتية': data['العدد'], 'اسم المرسل': sender_info
    }

    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=10)
        # تحديث الإحصائيات المحلية للتقرير
        stats = load_stats()
        stats['reports'].append({'المحافظة': data['المحافظة'], 'الفرقة': data['الفرقة'], 'العدد': data['العدد']})
        save_stats(stats)
        bot.reply_to(message, "✅ تم الحفظ بنجاح!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
