import os
import json
import threading
import requests
from datetime import datetime
from flask import Flask
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
STATS_FILE = 'stats.json'

bot = telebot.TeleBot(BOT_TOKEN)

# ── Flask health server (keeps Render alive / UptimeRobot ping) ──────────────
health_app = Flask(__name__)

@health_app.route('/')
@health_app.route('/api/healthz')
def healthz():
    return 'OK', 200

def run_health_server():
    port = int(os.environ.get('PORT', 8080))
    health_app.run(host='0.0.0.0', port=port)

# ── Stats helpers ─────────────────────────────────────────────────────────────
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {'total': 0, 'by_province': {}, 'by_activity': {}}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

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

# ── Bot handlers ──────────────────────────────────────────────────────────────
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "أهلاً بك! يمكنك إرسال البيانات مباشرة بصيغة نصية واحدة، "
        "أو بالضغط على الزر أدناه لإرسال التقرير:\n\n"
        "يرجى نسخ القالب التالي وملئه وإرساله في رسالة واحدة:\n\n"
        "المحافظة:\n"
        "المنطقة:\n"
        "التاريخ:\n"
        "اسم الفرقة:\n"
        "الفئة:\n"
        "نوع النشاط:\n"
        "اسم النشاط:\n"
        "اسم القائد:\n"
        "اسم مساعد القائد:\n"
        "عدد الفتية:"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("إرسال تقرير جديد"))
    bot.reply_to(message, welcome_text, reply_markup=markup)


@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا الأمر.")
        return
    stats = load_stats()
    total = stats.get('total', 0)
    if total == 0:
        bot.reply_to(message, "📊 لا توجد تقارير مسجلة حتى الآن.")
        return

    province_lines = "\n".join(
        [f"  • {p}: {c}" for p, c in sorted(stats.get('by_province', {}).items(), key=lambda x: -x[1])]
    ) or "  —"
    activity_lines = "\n".join(
        [f"  • {a}: {c}" for a, c in sorted(stats.get('by_activity', {}).items(), key=lambda x: -x[1])]
    ) or "  —"

    stats_text = (
        f"📊 *إحصائيات التقارير*\n\n"
        f"📋 إجمالي التقارير: *{total}*\n\n"
        f"🗺️ *توزيع حسب المحافظة:*\n{province_lines}\n\n"
        f"⚡ *توزيع حسب نوع النشاط:*\n{activity_lines}"
    )
    bot.reply_to(message, stats_text, parse_mode='Markdown')


@bot.message_handler(commands=['reset_stats'])
def reset_stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ غير مصرح لك باستخدام هذا الأمر.")
        return
    save_stats({"total": 0, "by_province": {}, "by_activity": {}})
    bot.reply_to(message, "✅ تمت إعادة تصفير الإحصائيات بنجاح.\n📊 العداد يبدأ الآن من الصفر.")


@bot.message_handler(func=lambda message: message.text == "إرسال تقرير جديد")
def request_report(message):
    template = (
        "قم بنسخ النص التالي، املأ الفراغات ثم أرسله:\n\n"
        "المحافظة: \n"
        "المنطقة: \n"
        "التاريخ: \n"
        "اسم الفرقة: \n"
        "الفئة: \n"
        "نوع النشاط: \n"
        "اسم النشاط: \n"
        "اسم القائد: \n"
        "اسم مساعد القائد: \n"
        "عدد الفتية: "
    )
    bot.reply_to(message, template)


@bot.message_handler(func=lambda message: True)
def handle_report(message):
    text = message.text
    lines = text.split('\n')

    def get_field(field_name):
        for line in lines:
            if line.strip().startswith(field_name):
                for sep in (':', '：'):
                    parts = line.split(sep, 1)
                    if len(parts) > 1:
                        return parts[1].strip()
        return ""

    data = {
        'المحافظة':        get_field('المحافظة'),
        'المنطقة':         get_field('المنطقة'),
        'التاريخ':         get_field('التاريخ'),
        'اسم الفرقة':      get_field('اسم الفرقة'),
        'الفئة':           get_field('الفئة'),
        'نوع النشاط':      get_field('نوع النشاط'),
        'اسم النشاط':      get_field('اسم النشاط'),
        'اسم القائد':      get_field('اسم القائد'),
        'اسم مساعد القائد': get_field('اسم مساعد القائد'),
        'عدد الفتية':      get_field('عدد الفتية'),
        'وقت التسجيل':     datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    required = [
        'المحافظة', 'المنطقة', 'التاريخ', 'اسم الفرقة',
        'الفئة', 'نوع النشاط', 'اسم النشاط', 'اسم القائد', 'عدد الفتية'
    ]
    missing = [f for f in required if not data[f]]
    if missing:
        bot.reply_to(
            message,
            f"⚠️ عذراً، لم يتم حفظ التقرير بسبب وجود حقول فارغة أو مفقودة:\n"
            f"❌ ({', '.join(missing)})\n\n"
            f"يرجى ملء كافة الحقول المذكورة وإعادة المحاولة."
        )
        return

    payload = {
        'date':           data['التاريخ'],
        'governorate':    data['المحافظة'],
        'region':         data['المنطقة'],
        'team_name':      data['اسم الفرقة'],
        'category':       data['الفئة'],
        'activity_type':  data['نوع النشاط'],
        'activity_name':  data['اسم النشاط'],
        'leader_name':    data['اسم القائد'],
        'assistant_name': data['اسم مساعد القائد'],
        'members_count':  data['عدد الفتية'],
        'timestamp':      data['وقت التسجيل'],
    }

    try:
        print(f"[DEBUG] Sending to Google Sheets: {payload}")
        response = requests.post(GOOGLE_SHEET_URL, json=payload, timeout=15, allow_redirects=False)
        print(f"[DEBUG] Initial status: {response.status_code}")

        if response.status_code in (301, 302, 303, 307, 308):
            redirect_url = response.headers.get('Location')
            response = requests.get(redirect_url, timeout=15)
            print(f"[DEBUG] Final status: {response.status_code}, body: {response.text[:200]}")

        response_text = response.text.strip()
        if '<html' in response_text.lower() or 'unable to open' in response_text.lower():
            print(f"[ERROR] Google returned HTML error: {response_text[:200]}")
            bot.reply_to(message, "❌ فشل الحفظ في Google Sheets. تحقق من إعدادات النشر.")
            return

        if response.status_code != 200:
            bot.reply_to(message, f"❌ فشل الحفظ. رمز الخطأ: {response.status_code}")
            return

        update_stats(data)
        bot.reply_to(message, "✅ تم استلام البيانات وحفظها في Google Sheets بنجاح!")

        sender = message.from_user
        sender_info = f"@{sender.username}" if sender.username else f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        stats = load_stats()
        notification = (
            f"🔔 *تقرير جديد* — #{stats['total']}\n"
            f"👤 المُرسِل: {sender_info} (ID: `{sender.id}`)\n"
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
        try:
            bot.send_message(ADMIN_ID, notification, parse_mode='Markdown')
        except Exception:
            pass

    except requests.exceptions.Timeout:
        bot.reply_to(message, "❌ انتهت مهلة الاتصال بـ Google Sheets. حاول مرة أخرى.")
    except Exception as e:
        print(f"[ERROR] {e}")
        bot.reply_to(message, f"❌ حدث خطأ أثناء إرسال البيانات: {str(e)}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    print(f"Health server started on port {os.environ.get('PORT', 8080)}")
    print("البوت يعمل الآن...")
    bot.infinity_polling()
