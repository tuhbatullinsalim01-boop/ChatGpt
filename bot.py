# -*- coding: utf-8 -*-
"""
ChatGPT-бот с контекстом (SQLite)
Запоминает историю диалога, умеет менять модель и системный промпт
"""

import os
import sqlite3
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import openai
from openai import OpenAI

# ========== КОНФИГУРАЦИЯ (ТВОИ ДАННЫЕ) ==========
TELEGRAM_TOKEN = "8602006844:AAEFpU-2yWR0SQJiC5IUvU3lBScm6hENPVw"
OPENAI_API_KEY = "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"
ADMIN_ID = 17194921  # твой Telegram ID для админ-функций

client = OpenAI(api_key=OPENAI_API_KEY)

# ========== БАЗА ДАННЫХ ==========
DB_NAME = "chat_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            model TEXT DEFAULT 'gpt-4o-mini',
            system_prompt TEXT DEFAULT 'Ты полезный и вежливый ассистент.'
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# ========== РАБОТА С БАЗОЙ ==========

def get_user_settings(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT model, system_prompt FROM user_settings WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    if result:
        return {"model": result[0], "system_prompt": result[1]}
    return {"model": "gpt-4o-mini", "system_prompt": "Ты полезный и вежливый ассистент."}

def save_user_settings(user_id, model=None, system_prompt=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    current = get_user_settings(user_id)
    new_model = model if model else current["model"]
    new_prompt = system_prompt if system_prompt else current["system_prompt"]
    cur.execute('''
        INSERT OR REPLACE INTO user_settings (user_id, model, system_prompt)
        VALUES (?, ?, ?)
    ''', (user_id, new_model, new_prompt))
    conn.commit()
    conn.close()

def get_chat_history(user_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        SELECT role, content FROM chat_history
        WHERE user_id = ?
        ORDER BY timestamp DESC LIMIT ?
    ''', (user_id, limit * 2))
    rows = cur.fetchall()
    conn.close()
    messages = []
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})
    return messages

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO chat_history (user_id, role, content)
        VALUES (?, ?, ?)
    ''', (user_id, role, content))
    conn.commit()
    conn.close()

def clear_history(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_user_count():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(DISTINCT user_id) FROM chat_history')
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT DISTINCT user_id FROM chat_history')
    users = cur.fetchall()
    conn.close()
    return [u[0] for u in users]

# ========== КОМАНДЫ ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🧠 Привет, {user.first_name}!\n\n"
        f"Я — ChatGPT с памятью. Я запоминаю всё, о чём мы говорили, и могу продолжать диалог.\n\n"
        f"📌 Команды:\n"
        f"/start — показать это меню\n"
        f"/clear — очистить историю диалога\n"
        f"/settings — настроить модель и системный промпт\n"
        f"/stats — показать статистику диалога\n\n"
        f"Просто напиши мне что-нибудь!"
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    clear_history(user_id)
    await update.message.reply_text("🗑️ История диалога очищена!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history = get_chat_history(user_id, limit=100)
    msg_count = len(history)
    settings = get_user_settings(user_id)
    await update.message.reply_text(
        f"📊 Статистика диалога:\n\n"
        f"👤 Пользователь: {update.effective_user.first_name}\n"
        f"💬 Сообщений в истории: {msg_count}\n"
        f"🧠 Модель: {settings['model']}\n"
        f"📝 Системный промпт: {settings['system_prompt'][:50]}..."
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🧠 Сменить модель", callback_data="change_model")],
        [InlineKeyboardButton("✍️ Изменить системный промпт", callback_data="change_prompt")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ Настройки бота:\n\n"
        "Выбери действие:",
        reply_markup=reply_markup
    )

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    # Проверяем, не ждём ли мы ввод промпта
    if context.user_data.get('awaiting_prompt'):
        new_prompt = user_message
        save_user_settings(user_id, system_prompt=new_prompt)
        context.user_data['awaiting_prompt'] = False
        await update.message.reply_text(
            f"✅ Системный промпт обновлён!\n\n"
            f"Теперь бот будет работать с инструкцией:\n"
            f"«{new_prompt}»"
        )
        return

    save_message(user_id, "user", user_message)

    settings = get_user_settings(user_id)
    model = settings["model"]
    system_prompt = settings["system_prompt"]

    history = get_chat_history(user_id, limit=10)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append(msg)
    if not messages or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000
        )
        reply = response.choices[0].message.content

        save_message(user_id, "assistant", reply)

        # Разбиваем длинные ответы на части (Telegram лимит 4096 символов)
        if len(reply) > 4000:
            for i in range(0, len(reply), 4000):
                await update.message.reply_text(reply[i:i+4000])
        else:
            await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# ========== ОБРАБОТЧИК КНОПОК ==========

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "change_model":
        keyboard = [
            [InlineKeyboardButton("GPT-4o-mini (быстрый, дешёвый)", callback_data="model_gpt-4o-mini")],
            [InlineKeyboardButton("GPT-4o (умный, дорогой)", callback_data="model_gpt-4o")],
            [InlineKeyboardButton("GPT-3.5-turbo (эконом)", callback_data="model_gpt-3.5-turbo")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🧠 Выбери модель:\n\n"
            "— GPT-4o-mini: быстрый и дешёвый\n"
            "— GPT-4o: умный, дорогой\n"
            "— GPT-3.5-turbo: экономный",
            reply_markup=reply_markup
        )

    elif data.startswith("model_"):
        model = data.replace("model_", "")
        save_user_settings(user_id, model=model)
        await query.edit_message_text(f"✅ Модель изменена на: {model}")

    elif data == "change_prompt":
        await query.edit_message_text(
            "✍️ Введите новый системный промпт:\n\n"
            "Например: «Ты — эксперт по Python, помогаешь писать код.»\n\n"
            "Пришли мне текст в следующем сообщении."
        )
        context.user_data['awaiting_prompt'] = True

    elif data == "back_to_settings":
        keyboard = [
            [InlineKeyboardButton("🧠 Сменить модель", callback_data="change_model")],
            [InlineKeyboardButton("✍️ Изменить системный промпт", callback_data="change_prompt")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ Настройки бота:",
            reply_markup=reply_markup
        )

    elif data == "back_to_menu":
        await start(update, context)

# ========== АДМИН-КОМАНДЫ ==========

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 Админ-панель", reply_markup=reply_markup)

async def admin_broadcast_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 РАССЫЛКА\n\n{text}")
            sent += 1
        except:
            pass
    await update.message.reply_text(f"✅ Рассылка отправлена {sent} пользователям.")

# ========== ЗАПУСК ==========

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 ChatGPT-бот с контекстом запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()