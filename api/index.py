import os
import html
import requests
from flask import Flask, request
import telebot
from telebot import types

# ===== الإعدادات (من متغيرات البيئة) =====
BOT_TOKEN ="8359352188:AAHV0d7p0QpX_5Pt023O4RUhFKxTzpKd9CY"
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzPTLOKo739xNiEEQ1-WKV9jMLhkm4KWQ7CWbebIQVpLoYdPCJS59wuuecbJtwI4g/exec"


bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

TITLES = {
    "stats_general": ("get_stats", "📊 <b>الإحصائيات العامة للمناطق:</b>"),
    "stats_monthly": ("get_monthly", "🗓️ <b>الإحصائيات الشهرية:</b>"),
    "stats_weekly": ("get_weekly", "📅 <b>الإحصائيات الأسبوعية:</b>"),
}


def fetch_data_from_sheet(action="get_stats"):
    """يرجّع (results, error). إذا صار فشل يرجّع error بدل رقم وهمي."""
    try:
        response = requests.get(
            GOOGLE_SHEET_URL,
            params={"action": action},
            timeout=30,
            allow_redirects=True,
        )
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:300])

        if response.status_code != 200:
            return None, f"خطأ HTTP {response.status_code}"

        try:
            data = response.json()
        except ValueError:
            return None, (
                "الرد مو JSON. غالباً النشر مو بصلاحية «أي شخص» "
                "أو الرابط قديم."
            )

        if not data.get("success"):
            return None, "السكربت رجّع success=false"

        results = data.get("results", [])
        if not results:
            return None, "ما وصلت بيانات من الشيت"
        return results, None

    except requests.exceptions.Timeout:
        return None, "انتهت مهلة الاتصال بالشيت"
    except Exception as e:
        print(f"Error: {e}")
        return None, f"خطأ: {e}"


def build_text(title, results):
    """يبني النص: العناصر مرتبة، والإجمالي بالآخر."""
    total_item = None
    items = []
    for item in results:
        if item.get("category") == "البيانات الكلية":
            total_item = item
        else:
            items.append(item)

    # الأسبوعي والشهري يترتبون بالاسم (تاريخ)، العام بالعدد
    items.sort(key=lambda x: x.get("category", ""))

    lines = [title, ""]
    for item in items:
        cat = html.escape(str(item.get("category", "أخرى")))
        lines.append(f"🔹 {cat}: <b>{item.get('count', 0)}</b>")
    if total_item:
        lines.append("")
        lines.append(f"✅ الإجمالي: <b>{total_item.get('count', 0)}</b>")
    return lines


def send_long(chat_id, lines):
    """تيليغرام يقبل 4096 حرف بالرسالة، نقسّم إذا طالت."""
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 3800:
            bot.send_message(chat_id, chunk, parse_mode="HTML")
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        bot.send_message(chat_id, chunk, parse_mode="HTML")


@app.route("/")
def index():
    return "Bot Server is Running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "", 200
    return "Forbidden", 403


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل الأمر /stats لعرض لوحة الإحصائيات.")


@bot.message_handler(commands=["stats"])
def stats_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات العامة للمناطق", callback_data="stats_general"),
        types.InlineKeyboardButton("🗓️ الإحصائيات الشهرية", callback_data="stats_monthly"),
        types.InlineKeyboardButton("📅 الإحصائيات الأسبوعية", callback_data="stats_weekly"),
    )
    bot.send_message(
        message.chat.id,
        "📁 <b>اختر نوع الإحصائيات المطلوبة:</b>",
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id)

    action, title = TITLES.get(call.data, TITLES["stats_general"])
    results, error = fetch_data_from_sheet(action)

    if error:
        bot.send_message(call.message.chat.id, f"⚠️ {html.escape(error)}")
        return

    send_long(call.message.chat.id, build_text(title, results))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
