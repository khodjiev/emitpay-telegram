import os
import re
import datetime as dt
from dotenv import load_dotenv
import telebot
from telebot import types

from db import init_db, add_record, get_records
from report import make_report_xlsx, make_text_summary

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в окружении. Создай .env и положи туда BOT_TOKEN=...")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='Markdown')
init_db()

USER_STATE = {}  # user_id -> {'mode': 'income'|'expense', 'await': 'category'|'amount', 'category': str}

def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("➖ Расход"), types.KeyboardButton("➕ Доход"))
    kb.row(types.KeyboardButton("📊 Отчёт"))
    return kb

def report_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Последние 7 дней", callback_data="report:7d"))
    kb.add(types.InlineKeyboardButton("Этот месяц", callback_data="report:this_month"))
    kb.add(types.InlineKeyboardButton("Прошлый месяц", callback_data="report:last_month"))
    kb.add(types.InlineKeyboardButton("Произвольный период", callback_data="report:custom"))
    return kb

@bot.message_handler(commands=['start','menu'])
def cmd_start(message: types.Message):
    bot.send_message(message.chat.id, "Привет! Я помогу вести учёт доходов и расходов.\nВыбери действие:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["➖ Расход","➕ Доход"])
def handle_kind(message: types.Message):
    mode = 'expense' if "Расход" in message.text else 'income'
    USER_STATE[message.from_user.id] = {'mode': mode, 'await': 'category'}
    bot.send_message(message.chat.id, "Введи *категорию/описание* (например: еда, аренда, зарплата)...")

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get('await') == 'category')
def get_category(message: types.Message):
    st = USER_STATE.get(message.from_user.id)
    if not st: return
    st['category'] = message.text.strip()
    st['await'] = 'amount'
    bot.send_message(message.chat.id, "Теперь введи *сумму* (например: 125000.50):")

def parse_amount(text: str):
    text = text.replace(",", ".").strip()
    if not re.match(r"^-?\d+(\.\d+)?$", text):
        return None
    return float(text)

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get('await') == 'amount')
def get_amount(message: types.Message):
    st = USER_STATE.get(message.from_user.id)
    if not st: return
    amount = parse_amount(message.text)
    if amount is None:
        bot.send_message(message.chat.id, "Не похоже на число. Введи сумму наподобие `125000.50`")
        return
    add_record(message.from_user.id, st['mode'], st['category'], amount)
    mode_emoji = "➖" if st['mode']=='expense' else "➕"
    bot.send_message(message.chat.id, f"{mode_emoji} Записал: *{st['category']}* — *{amount:.2f}*", reply_markup=main_menu())
    USER_STATE.pop(message.from_user.id, None)

@bot.message_handler(func=lambda m: m.text == "📊 Отчёт")
def ask_report(message: types.Message):
    bot.send_message(message.chat.id, "Выбери период:", reply_markup=report_menu())

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("report:"))
def report_period(c: types.CallbackQuery):
    action = c.data.split(":",1)[1]
    chat_id = c.message.chat.id
    user_id = c.from_user.id

    today = dt.date.today()
    if action == "7d":
        start = today - dt.timedelta(days=7)
        end = today + dt.timedelta(days=1)
        send_report(chat_id, user_id, start, end)
    elif action == "this_month":
        start = today.replace(day=1)
        if start.month == 12:
            end = dt.date(start.year+1, 1, 1)
        else:
            end = dt.date(start.year, start.month+1, 1)
        send_report(chat_id, user_id, start, end)
    elif action == "last_month":
        first_this = today.replace(day=1)
        end = first_this
        prev_month_last_day = first_this - dt.timedelta(days=1)
        start = prev_month_last_day.replace(day=1)
        send_report(chat_id, user_id, start, end)
    elif action == "custom":
        bot.answer_callback_query(c.id)
        bot.send_message(chat_id, "Введи период в формате: `YYYY-MM-DD YYYY-MM-DD` (начало и конец включительно). Пример: `2025-09-01 2025-09-29`")
        USER_STATE[user_id] = {'await': 'custom_range'}
    else:
        bot.answer_callback_query(c.id, "Неизвестный период")

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get('await') == 'custom_range')
def handle_custom_range(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.strip().split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "Нужно две даты через пробел: `YYYY-MM-DD YYYY-MM-DD`")
        return
    try:
        start = dt.datetime.strptime(parts[0], "%Y-%m-%d").date()
        end_inclusive = dt.datetime.strptime(parts[1], "%Y-%m-%d").date()
        end = end_inclusive + dt.timedelta(days=1)
    except ValueError:
        bot.send_message(message.chat.id, "Дата должна быть в формате `YYYY-MM-DD`. Попробуй ещё раз.")
        return
    send_report(message.chat.id, user_id, start, end)
    USER_STATE.pop(user_id, None)

def send_report(chat_id: int, user_id: int, start: dt.date, end: dt.date):
    start_iso = dt.datetime.combine(start, dt.time.min).isoformat()
    end_iso = dt.datetime.combine(end, dt.time.min).isoformat()
    rows = get_records(user_id, start_iso, end_iso)
    text = make_text_summary(rows)
    bot.send_message(chat_id, text)
    path = make_report_xlsx(rows, out_dir_path(), user_id, start, end - dt.timedelta(days=1))
    with open(path, "rb") as f:
        bot.send_document(chat_id, f, visible_file_name=path.name, caption="Экспорт Excel")

def out_dir_path():
    from pathlib import Path
    p = Path(__file__).parent / "exports"
    p.mkdir(exist_ok=True, parents=True)
    return p

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True)
