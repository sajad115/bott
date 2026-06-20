import os
import json
import requests
from flask import Flask, request
import telebot
from telebot import types

# الإعدادات من Vercel Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1682496497'))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

PROVINCES = ["بغداد", "البصرة", "الموصل", "أربيل", "الأنبار", "أخرى"]

def is_admin(chat_id):
    return chat_id == ADMIN_ID

@app.route('/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return '', 200

# --- الأوامر الأساسية ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("إرسال تقرير جديد"))
    if is_admin(message.chat.id):
        markup.add(types.KeyboardButton("بحث عن تقارير"))
    bot.send_message(message.chat.id, "أهلاً بك! استخدم الأزرار أدناه:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "إرسال تقرير جديد")
def report_start(message):
    markup = types.InlineKeyboardMarkup()
    for prov in PROVINCES:
        markup.add(types.InlineKeyboardButton(prov, callback_data=f"prov_{prov}"))
    bot.send_message(message.chat.id, "اختر المحافظة:", reply_markup=markup)

# --- معالج أزرار المحافظات ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("prov_"))
def callback_province(call):
    province_name = call.data.split("_")[1]
    bot.answer_callback_query(call.id, f"تم اختيار: {province_name}")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"تم اختيار *{province_name}* ✅\n\nالآن أرسل تفاصيل التقرير في رسالة واحدة (المنطقة، التاريخ، اسم الفرقة، نوع النشاط، اسم القائد، عدد الفتية):",
        parse_mode='Markdown'
    )

# --- أوامر الأدمن ---
@bot.message_handler(commands=['search'])
@bot.message_handler(func=lambda message: message.text == "بحث عن تقارير")
def search_cmd(message):
    if not is_admin(message.chat.id):
        return bot.reply_to(message, "❌ هذا الأمر مخصص للإدارة فقط.")
    bot.reply_to(message, "🔍 ميزة البحث مفعلة. (يتم الربط الآن بجدول البيانات...)")

if __name__ == '__main__':
    app.run()
