import os
import re
import html
import calendar
from datetime import datetime
import requests
from flask import Flask, request
import telebot
from telebot import types

# ===== الإعدادات (من متغيرات البيئة) =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
GOOGLE_SHEET_URL = os.environ["GOOGLE_SHEET_URL"].strip()

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

TITLES = {
    "stats_general": ("get_stats", "📊 <b>الإحصائيات العامة للمناطق:</b>"),
    "stats_weekly": ("get_weekly", "📅 <b>إحصائيات هذا الأسبوع:</b>"),
}

DATE_RE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}")

MONTHS_AR = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران",
             "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]


def month_label(ym):
    y, m = ym.split("-")
    return f"{MONTHS_AR[int(m) - 1]} {y}"


def fetch_data_from_sheet(action="get_stats", extra=None):
    """يرجّع (data, error). إذا صار فشل يرجّع error بدل رقم وهمي."""
    params = {"action": action}
    if extra:
        params.update(extra)
    try:
        response = requests.get(
            GOOGLE_SHEET_URL, params=params, timeout=30, allow_redirects=True
        )
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:300])

        if response.status_code != 200:
            return None, f"خطأ HTTP {response.status_code}"

        try:
            data = response.json()
        except ValueError:
            return None, "الرد مو JSON. تأكد من رابط النشر وصلاحية «أي شخص»."

        if not data.get("success"):
            return None, "السكربت رجّع خطأ: " + str(data.get("error", ""))

        if not data.get("results"):
            return None, "ما وصلت بيانات من الشيت"
        return data, None

    except requests.exceptions.Timeout:
        return None, "انتهت مهلة الاتصال بالشيت"
    except Exception as e:
        print(f"Error: {e}")
        return None, f"خطأ: {e}"


def build_text(title, data):
    results = data.get("results", [])
    total_item = None
    items = []
    for item in results:
        if item.get("category") == "البيانات الكلية":
            total_item = item
        else:
            items.append(item)

    # الأكثر عدداً أولاً
    items.sort(key=lambda x: x.get("count", 0), reverse=True)

    lines = [title]
    if data.get("period"):
        lines.append(f"🗓️ الفترة: {html.escape(data['period'])}")
    lines.append("")

    if not items:
        lines.append("ما توجد بيانات بهذي الفترة.")
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


def normalize_date(s):
    """يقبل 2026-11-01 أو 01/11/2026 ويرجّع yyyy-MM-dd"""
    if "-" in s:
        y, m, d = s.split("-")
    else:
        d, m, y = s.split("/")
    return datetime(int(y), int(m), int(d)).strftime("%Y-%m-%d")


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
        types.InlineKeyboardButton("📅 إحصائيات هذا الأسبوع", callback_data="stats_weekly"),
        types.InlineKeyboardButton("📆 بين تاريخين", callback_data="stats_range"),
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

    if call.data == "stats_range":
        bot.send_message(
            call.message.chat.id,
            "📆 ارسل التاريخين بهالشكل:\n\n"
            "<code>2026-11-01 2026-11-08</code>\n\n"
            "أو: <code>01/11/2026 08/11/2026</code>",
            parse_mode="HTML",
        )
        return

    # عرض الشهور المتوفرة كأزرار
    if call.data == "stats_monthly":
        data, error = fetch_data_from_sheet("get_months")
        if error:
            bot.send_message(call.message.chat.id, f"⚠️ {html.escape(error)}")
            return
        months = [i for i in data["results"]
                  if re.fullmatch(r"\d{4}-\d{2}", str(i.get("category", "")))]
        months.sort(key=lambda x: x["category"], reverse=True)
        months = months[:12]
        if not months:
            bot.send_message(call.message.chat.id, "ما لقيت شهور بالشيت.")
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(*[
            types.InlineKeyboardButton(
                f"{month_label(i['category'])} ({i['count']})",
                callback_data="month_" + i["category"],
            ) for i in months
        ])
        bot.send_message(call.message.chat.id, "🗓️ <b>اختر الشهر:</b>",
                         reply_markup=markup, parse_mode="HTML")
        return

    # إحصائيات الشهر المختار
    if call.data.startswith("month_"):
        ym = call.data[len("month_"):]
        y, m = map(int, ym.split("-"))
        last = calendar.monthrange(y, m)[1]
        data, error = fetch_data_from_sheet(
            "get_range", {"from": f"{y}-{m:02d}-01", "to": f"{y}-{m:02d}-{last}"}
        )
        if error:
            bot.send_message(call.message.chat.id, f"⚠️ {html.escape(error)}")
            return
        send_long(call.message.chat.id,
                  build_text(f"🗓️ <b>إحصائيات {month_label(ym)}:</b>", data))
        return

    action, title = TITLES.get(call.data, TITLES["stats_general"])
    data, error = fetch_data_from_sheet(action)

    if error:
        bot.send_message(call.message.chat.id, f"⚠️ {html.escape(error)}")
        return

    send_long(call.message.chat.id, build_text(title, data))


# أي رسالة نصية فيها تاريخين = طلب إحصائيات بين تاريخين
@bot.message_handler(func=lambda m: bool(m.text) and len(DATE_RE.findall(m.text)) == 2)
def handle_range(message):
    raw_from, raw_to = DATE_RE.findall(message.text)
    try:
        date_from = normalize_date(raw_from)
        date_to = normalize_date(raw_to)
    except ValueError:
        bot.reply_to(message, "⚠️ التاريخ غير صحيح. مثال: 2026-11-01 2026-11-08")
        return

    data, error = fetch_data_from_sheet("get_range", {"from": date_from, "to": date_to})
    if error:
        bot.reply_to(message, f"⚠️ {html.escape(error)}")
        return

    send_long(message.chat.id, build_text("📆 <b>الإحصائيات بين تاريخين:</b>", data))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
