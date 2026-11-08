import os
import json
import requests
from flask import Flask, request
import telebot
from telebot import types
BOT_TOKEN = "8359352188:AAHV0d7p0QpX_5Pt023O4RUhFKxTzpKd9CY"
# رابط الـ Web App الخاص بـ Google Apps Script
GOOGLE_SHEET_URL = 'https://script.google.com/macros/s/AKfycbzPTLOKo739xNIeEQE1-WKV9jvMLhkvm4KWQ7CWbebIQVpLoYydPCJS59wuuecbJtwI4g/exec'
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# --- دالة مساعدة لجلب البيانات من Google Sheets مع تتبع التوجيهات (redirects) ---
def fetch_data_from_sheet(action, query=""):
    try:
        url = f"{GOOGLE_SHEET_URL}?action={action}&query={query}"
        # إضافة Headers وهمية لكي لا يقوم جوجل برفض الطلب كبوت
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
        print(f"Google Script Status Code: {response.status_code}")
        print(f"Google Script Response Text: {response.text[:200]}") # طباعة أول 200 حرف من الاستجابة لمعرفة المشكلة
        
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
    return None

# --- الأوامر الأساسية ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في بوت الإحصائيات والاستعلامات 📊\n\n"
        "يمكنك استخدام الأوامر التالية:\n"
        "/stats - لعرض الإحصائيات العامة الشاملة من الشيت\n"
        "/search [كلمة البحث] - للبحث عن بيانات محددة\n"
        "أو اضغط على الزر أدناه للحصول على الإحصائيات."
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📊 الإحصائيات العامة"))
    bot.reply_to(message, welcome_text, reply_markup=markup)

# --- أمر الإحصائيات الشاملة ---
@bot.message_handler(commands=['stats'])
@bot.message_handler(func=lambda message: message.text == "📊 الإحصائيات العامة")
def send_stats(message):
    processing_msg = bot.reply_to(message, "⏳ جاري جلب الإحصائيات من قاعدة البيانات...")
    
    data = fetch_data_from_sheet("get_stats")
    
    if not data or not data.get('success'):
        bot.edit_message_text("❌ حدث خطأ أثناء جلب البيانات أو أن الشيت فارغ.", message.chat.id, processing_msg.message_id)
        return

    results = data.get('results', [])
    if not results:
        bot.edit_message_text("ℹ️ لا توجد إحصائيات متاحة حالياً.", message.chat.id, processing_msg.message_id)
        return

    stats_text = "📊 *الإحصائيات الشاملة من قاعدة البيانات:*\n\n"
    for item in results:
        stats_text += f"🔹 *{item.get('category')}*: {item.get('count')} نشاط\n"
    
    bot.edit_message_text(stats_text, message.chat.id, processing_msg.message_id, parse_mode='Markdown')

# --- أمر البحث المخصص ---
@bot.message_handler(commands=['search'])
def search_records(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ يرجى كتابة كلمة البحث بعد الأمر.\nمثال: `/search بغداد`", parse_mode='Markdown')
        return
    
    query = args[1]
    processing_msg = bot.reply_to(message, f"🔍 جاري البحث عن: `{query}`...", parse_mode='Markdown')
    
    data = fetch_data_from_sheet("search", query)
    
    if not data or not data.get('success') or not data.get('results'):
        bot.edit_message_text(f"❌ لم يتم العثور على نتائج مطابقة لـ: `{query}`", message.chat.id, processing_msg.message_id, parse_mode='Markdown')
        return

    results = data.get('results')
    response = f"🔍 *نتائج البحث عن ({query}):*\n\n"
    for r in results[:10]:
        response += f"📌 {r.get('title', 'نشاط')} - {r.get('date', '')} ({r.get('province', '')})\n"
    
    bot.edit_message_text(response, message.chat.id, processing_msg.message_id, parse_mode='Markdown')

# --- معالجة الـ Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return '', 200
    return 'Forbidden', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
