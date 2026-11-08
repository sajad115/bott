import os
import json
import requests
from flask import Flask, request
import telebot
from telebot import types

BOT_TOKEN = "8359352188:AAHV0d7p0QpX_5Pt023O4RUhFKxTzpKd9CY"
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzPTLOKo739xNiEEQ1-WKV9jMLhkm4KWQ7CWbebIQVpLoYdPCJS59wuuecbJtwI4g/exec"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

def fetch_data_from_sheet(action, query=""):
    try:
        url = f"{GOOGLE_SHEET_URL}?action={action}&query={query}"
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error: {e}")
    return {"success": False, "message": "خطأ في الاتصال"}

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
        return 'Forbidden', 403

# أمر /stats يعرض قائمة أزرار اختيار نوع الإحصئيات
@bot.message_handler(commands=['stats'])
def stats_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات العامة للمناطق", callback_data="stats_general"),
        types.InlineKeyboardButton("🗓️ الإحصائيات الشهرية", callback_data="stats_monthly"),
        types.InlineKeyboardButton("📅 الإحصائيات الأسبوعية/اليومية", callback_data="stats_weekly")
    )
    bot.send_message(message.chat.id, "📁 **اختر نوع الإحصائيات المطلوبة:**", reply_markup=markup, parse_mode="Markdown")

# التعامل مع الأزرار التفاعلية
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    bot.answer_callback_query(call.id)
    action = "get_stats"
    title = "📊 **الإحصائيات العامة:**"
    
    if call.data == "stats_general":
        action = "get_stats"
        title = "📊 **الإحصائيات العامة للمناطق:**"
    elif call.data == "stats_monthly":
        action = "get_monthly"
        title = "🗓️ **الإحصائيات الشهرية:**"
    elif call.data == "stats_weekly":
        action = "get_weekly"
        title = "📅 **الإحصائيات الأسبوعية:**"
        
    data = fetch_data_from_sheet(action)
    
    if data and data.get("success") and "results" in data and data["results"]:
        results = data["results"]
        response_text = f"{title}\n\n"
        for item in results:
            response_text += f"🔹 {item.get('category', 'أخرى')}: **{item.get('count', 0)}**\n"
        bot.send_message(call.message.chat.id, response_text, parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, "⚠️ لا توجد بيانات متاحة حالياً.")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل الأمر /stats لعرض لوحة الإحصائيات المتقدمة.")

if __name__ == "__main__":
    app.run()
