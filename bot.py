import os
import json
import requests
from flask import Flask, request
import telebot
from telebot import types

# التوكن المباشر الخاص بك
BOT_TOKEN = "8359352188:AAHV0d7p0QpX_5Pt023O4RUhFKxTzpKd9CY"
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbzPTLOKo739xNiEEQ1-WKV9jMLhkm4KWQ7CWbebIQVpLoYdPCJS59wuuecbJtwI4g/exec"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# دالة جلب البيانات من Google Apps Script مع إرجاع رسالة الخطأ إن وجدت
def fetch_data_from_sheet(action, query=""):
    try:
        url = f"{GOOGLE_SHEET_URL}?action={action}&query={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return data
    except Exception as e:
        print(f"Error fetching sheet: {e}")
    return {"success": False, "message": "خطأ في الاتصال بالرابط"}

# مسار استقبال الـ Webhook من تيليجرام
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

# دالة التعامل مع أمر /stats لجلب وعرض الإحصائيات
@bot.message_handler(commands=['stats'])
def send_stats(message):
    bot.reply_to(message, "⏳ جاري جلب الإحصائيات من الجوجل شيت...")
    data = fetch_data_from_sheet("get_stats")
    
    if data and data.get("success") and "results" in data and data["results"]:
        results = data["results"]
        response_text = "📊 **إحصائيات المناطق:**\n\n"
        for item in results:
            response_text += f"🔹 {item.get('category', 'أخرى')}: **{item.get('count', 0)}**\n"
        bot.send_message(message.chat.id, response_text, parse_mode="Markdown")
    else:
        error_msg = data.get("message") or data.get("error") if data else "الشيت فارغ أو لم يتم العثور على بيانات"
        bot.send_message(message.chat.id, f"⚠️ تنبيه: {error_msg}")

# دالة الترحيب والأوامر العامة
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك! أرسل الأمر /stats لعرض الإحصائيات مباشرة من شيت البيانات.")

if __name__ == "__main__":
    app.run()
