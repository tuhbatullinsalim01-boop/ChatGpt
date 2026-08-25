# -*- coding: utf-8 -*-
"""
Starsov Bot — новый интерфейс (как Империя Звёзд)
"""

import os
import sqlite3
import json
import random
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8994877813:AAE-OvDCk9F-v5x01Ak-RWiktFyNxD7x0t4"
ADMIN_ID = 5141751465
SUPPORT_USERNAME = "mirrey5"
CHANNEL_USERNAME = "starsovoff"

SBP_NAME = "Салим Т."
SBP_BANK = "Сбербанк"
SBP_PHONE = "+7(939) 315-86-67"

# ========== БАЗА ДАННЫХ ==========
DB_NAME = "starsov.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref_code TEXT,
            referrer_id INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_balance REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TEXT,
            challenge_progress INTEGER DEFAULT 0,
            challenge_completed TEXT,
            reg_date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bonus_balance (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ========== РАБОТА С БАЗОЙ ==========
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cur.fetchone()

def create_user(user_id, username, referrer_id=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    ref_code = f"r{user_id}"
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, ref_code, referrer_id, reg_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, ref_code, referrer_id, datetime.now().strftime('%d.%m.%Y %H:%M')))
    
    if referrer_id:
        cur.execute('UPDATE users SET ref_balance = ref_balance + 0.1, ref_count = ref_count + 1 WHERE user_id = ?', (referrer_id,))
    
    cur.execute('INSERT OR IGNORE INTO bonus_balance (user_id, balance) VALUES (?, 0)', (user_id,))
    conn.commit()
    conn.close()
    
    add_bonus_balance(user_id, 3)

def add_bonus_balance(user_id, amount):
    if amount == 0: return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE bonus_balance SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_bonus_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT balance FROM bonus_balance WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_ref_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT ref_balance FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0.0

def get_ref_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT ref_count FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def create_order(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO orders (user_id, amount, date) VALUES (?, ?, ?)',
                (user_id, amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_orders_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM orders WHERE user_id = ?', (user_id,))
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = "completed"', (user_id,))
    completed = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = "pending"', (user_id,))
    pending = cur.fetchone()[0]
    cur.execute('SELECT SUM(amount) FROM orders WHERE user_id = ? AND status = "completed"', (user_id,))
    stars_bought = cur.fetchone()[0] or 0
    conn.close()
    return total, completed, pending, stars_bought

def get_pending_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT id, user_id, amount, date FROM orders WHERE status = "pending" ORDER BY date ASC')
    return cur.fetchall()

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def create_withdrawal(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO withdrawals (user_id, amount, date) VALUES (?, ?, ?)',
                (user_id, amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT id, user_id, amount, date FROM withdrawals WHERE status = "pending" ORDER BY date ASC')
    return cur.fetchall()

def update_withdrawal_status(w_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (status, w_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM users')
    return [u[0] for u in cur.fetchall()]

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    users = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM orders')
    orders = cur.fetchone()[0]
    cur.execute('SELECT SUM(amount) FROM orders WHERE status = "pending"')
    pending = cur.fetchone()[0] or 0
    cur.execute('SELECT SUM(amount) FROM orders WHERE status = "completed"')
    completed = cur.fetchone()[0] or 0
    cur.execute('SELECT SUM(balance) FROM bonus_balance')
    total_bonus = cur.fetchone()[0] or 0
    conn.close()
    return users, orders, pending, completed, total_bonus

def get_daily_streak(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT daily_streak, last_daily FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return (result[0], result[1]) if result else (0, None)

def set_daily_streak(user_id, streak, last_daily):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE users SET daily_streak = ?, last_daily = ? WHERE user_id = ?', (streak, last_daily, user_id))
    conn.commit()
    conn.close()

def get_challenge_progress(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT challenge_progress, challenge_completed FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return (result[0], result[1]) if result else (0, None)

def update_challenge_progress(user_id, progress, completed_date):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE users SET challenge_progress = ?, challenge_completed = ? WHERE user_id = ?', (progress, completed_date, user_id))
    conn.commit()
    conn.close()

# ========== ОТПРАВКА ЗВЁЗД ЧЕРЕЗ API ==========
async def send_stars(bot, user_id, amount):
    try:
        await bot.send_stars(
            chat_id=user_id,
            stars_count=amount,
            caption="⭐ Твой заказ выполнен! Спасибо, что выбрал Starsov! 🚀"
        )
        return True
    except Exception as e:
        print(f"Ошибка отправки звёзд: {e}")
        return False

# ========== ОФОРМЛЕНИЕ ==========
def format_message(title, body):
    return f"━━━━━━━━━━━━━━━━━━━\n🌟 **STARSOV**\n━━━━━━━━━━━━━━━━━━━\n{title}\n\n{body}\n━━━━━━━━━━━━━━━━━━━"

# ========== КНОПКИ ==========
def main_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить звёзды", callback_data="buy_stars")],
        [InlineKeyboardButton("📤 Продать звёзды", callback_data="sell_stars")],
        [InlineKeyboardButton("🎁 Подарки", callback_data="gifts")],
        [InlineKeyboardButton("👑 Telegram Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton("📊 Калькулятор", callback_data="calculator")],
        [InlineKeyboardButton("🤖 Создать бота", callback_data="create_bot")],
    ])
    return markup

def stars_amount_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("15 ★ — 23 ₽", callback_data="stars_15")],
        [InlineKeyboardButton("50 ★ — 76 ₽", callback_data="stars_50")],
        [InlineKeyboardButton("100 ★ — 152 ₽", callback_data="stars_100")],
        [InlineKeyboardButton("250 ★ — 380 ₽", callback_data="stars_250")],
        [InlineKeyboardButton("500 ★ — 760 ₽", callback_data="stars_500")],
        [InlineKeyboardButton("1000 ★ — 1 520 ₽", callback_data="stars_1000")],
        [InlineKeyboardButton("5000 ★ — 7 600 ₽", callback_data="stars_5000")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def payment_menu(order_type, amount):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 СБП (Рубли)", callback_data=f"pay_sbp_{order_type}_{amount}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def games_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏀 Баскет", callback_data="game_basket")],
        [InlineKeyboardButton("🎯 Дартс", callback_data="game_darts")],
        [InlineKeyboardButton("⚽ Футбол", callback_data="game_football")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def game_prize_menu(game):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("15 ★ (ставка 7 ★)", callback_data=f"prize_{game}_15_7")],
        [InlineKeyboardButton("25 ★ (ставка 12 ★)", callback_data=f"prize_{game}_25_12")],
        [InlineKeyboardButton("50 ★ (ставка 25 ★)", callback_data=f"prize_{game}_50_25")],
        [InlineKeyboardButton("100 ★ (ставка 50 ★)", callback_data=f"prize_{game}_100_50")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def withdrawal_amount_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("15 ★", callback_data="withdraw_15")],
        [InlineKeyboardButton("20 ★", callback_data="withdraw_20")],
        [InlineKeyboardButton("50 ★", callback_data="withdraw_50")],
        [InlineKeyboardButton("100 ★", callback_data="withdraw_100")],
        [InlineKeyboardButton("Своя сумма", callback_data="withdraw_custom")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def admin_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("📤 Выводы", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

# ========== КОМАНДЫ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    referrer_id = 0
    
    if len(update.message.text.split()) > 1:
        try:
            ref = update.message.text.split()[1]
            if ref.startswith("r"):
                referrer_id = int(ref[1:])
        except:
            pass
    
    if not get_user(user_id):
        create_user(user_id, username, referrer_id)
    
    balance = get_bonus_balance(user_id)
    await update.message.reply_text(
        f"🌟 **Добро пожаловать в Starsov!**\n\n"
        f"🔒 Текущий баланс: {balance} ★\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "back":
        balance = get_bonus_balance(user_id)
        await query.edit_message_text(
            f"🌟 **Добро пожаловать в Starsov!**\n\n"
            f"🔒 Текущий баланс: {balance} ★\n\n"
            f"Выберите действие:",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПРОФИЛЬ =====
    if data == "profile":
        user = get_user(user_id)
        username = user[1] if user else "Неизвестно"
        reg_date = user[8] if user else "Неизвестно"
        balance = get_bonus_balance(user_id)
        total, completed, pending, stars_bought = get_user_orders_count(user_id)
        
        text = f"👤 **Профиль**\n\n"
        text += f"🆔 ID: {user_id}\n"
        text += f"👤 Username: @{username}\n\n"
        text += f"💰 Баланс: {balance} ★\n"
        text += f"📥 Общий депозит: {stars_bought} ★\n\n"
        text += f"📦 **Заказы:**\n"
        text += f"• Всего: {total}\n"
        text += f"• Выполнено: {completed}\n"
        text += f"• В обработке: {pending}\n"
        text += f"• Куплено звёзд: {stars_bought} ★\n\n"
        text += f"📅 Регистрация: {reg_date}"
        
        await query.edit_message_text(
            text,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПОДДЕРЖКА =====
    if data == "support":
        await query.edit_message_text(
            f"📞 **Поддержка**\n\n"
            f"По всем вопросам обращайтесь:\n"
            f"👤 @{SUPPORT_USERNAME}\n\n"
            f"Мы ответим в ближайшее время!",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ИНФОРМАЦИЯ =====
    if data == "info":
        await query.edit_message_text(
            f"ℹ️ **Информация**\n\n"
            f"🌟 Starsov — бот для покупки Telegram Stars.\n\n"
            f"📌 Мы предлагаем:\n"
            f"• Покупку звёзд по выгодному курсу\n"
            f"• Telegram Premium\n"
            f"• Подарки друзьям\n"
            f"• Бонусную программу\n\n"
            f"📅 Версия: 2.0",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== КАЛЬКУЛЯТОР =====
    if data == "calculator":
        await query.edit_message_text(
            f"📊 **Калькулятор**\n\n"
            f"Цена: 1 ★ = 1.52 ₽\n\n"
            f"Примеры:\n"
            f"15 ★ = 23 ₽\n"
            f"50 ★ = 76 ₽\n"
            f"100 ★ = 152 ₽\n"
            f"250 ★ = 380 ₽\n"
            f"500 ★ = 760 ₽\n"
            f"1000 ★ = 1 520 ₽\n"
            f"5000 ★ = 7 600 ₽",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== СОЗДАТЬ БОТА =====
    if data == "create_bot":
        await query.edit_message_text(
            f"🤖 **Создать бота**\n\n"
            f"Хотите создать своего бота для продажи звёзд?\n\n"
            f"📌 Напишите @{SUPPORT_USERNAME} для консультации.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПОПОЛНИТЬ БАЛАНС =====
    if data == "deposit":
        await query.edit_message_text(
            f"💰 **Пополнить баланс**\n\n"
            f"Пополнение баланса через СБП:\n"
            f"📱 {SBP_PHONE}\n"
            f"🏦 {SBP_BANK}\n"
            f"👤 {SBP_NAME}\n\n"
            f"После оплаты напишите в поддержку @{SUPPORT_USERNAME}",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== КУПИТЬ ЗВЁЗДЫ =====
    if data == "buy_stars":
        await query.edit_message_text(
            f"⭐ **Купить звёзды**\n\n"
            f"Выберите количество:",
            reply_markup=stars_amount_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("stars_"):
        amount = int(data.split("_")[1])
        price_rub = amount * 1.52
        await query.edit_message_text(
            f"⭐ **Покупка {amount} ★**\n\n"
            f"💳 Стоимость: {price_rub:.2f} ₽\n\n"
            f"Выберите способ оплаты:",
            reply_markup=payment_menu("stars", amount),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПРОДАЖА ЗВЁЗД (ВЫВОД) =====
    if data == "sell_stars":
        bonus = get_bonus_balance(user_id)
        await query.edit_message_text(
            f"📤 **Продажа звёзд**\n\n"
            f"🎁 Доступно для вывода: {bonus} ★\n\n"
            f"Минимальная сумма — 15 ★\n"
            f"Выберите сумму:",
            reply_markup=withdrawal_amount_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("withdraw_"):
        parts = data.split("_")
        if parts[1] == "custom":
            await query.edit_message_text(
                f"💸 **Введите сумму**\n\n"
                f"Введите количество звёзд для вывода (минимум 15):",
                parse_mode="Markdown"
            )
            context.user_data['withdraw_custom'] = True
            return
        
        amount = int(parts[1])
        bonus = get_bonus_balance(user_id)
        
        if amount < 15:
            await query.edit_message_text(
                f"❌ **Ошибка**\n\nМинимальная сумма — 15 ★.",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if amount > bonus:
            await query.edit_message_text(
                f"❌ **Недостаточно звёзд!**\n\n"
                f"У тебя {bonus} ★, а нужно {amount} ★.",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        create_withdrawal(user_id, amount)
        add_bonus_balance(user_id, -amount)
        
        await query.edit_message_text(
            f"✅ **Заявка на вывод создана!**\n\n"
            f"Сумма: {amount} ★\n\n"
            f"Администратор проверит заявку.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        
        await context.bot.send_message(
            ADMIN_ID,
            f"📤 **НОВАЯ ЗАЯВКА НА ВЫВОД**\n\n"
            f"👤 Пользователь: @{query.from_user.username or 'без юзернейма'}\n"
            f"🆔 ID: {user_id}\n"
            f"💰 Сумма: {amount} ★\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
        return
    
    # ===== ПОКУПКА ПРЕМИУМ =====
    if data == "buy_premium":
        await query.edit_message_text(
            f"👑 **Telegram Premium**\n\n"
            f"Выберите срок:\n\n"
            f"3 мес. — 989 ₽ (651 ★)\n"
            f"6 мес. — 1 219 ₽ (802 ★)\n"
            f"12 мес. — 2 130 ₽ (1 401 ★)\n\n"
            f"Напишите в поддержку @{SUPPORT_USERNAME} для оформления.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ОПЛАТА (СБП) =====
    if data.startswith("pay_"):
        parts = data.split("_")
        order_type = parts[1]
        amount = int(parts[2])
        
        create_order(user_id, amount)
        
        text = f"🇷🇺 **Оплата по СБП**\n\n"
        text += f"Заказ: {order_type} на {amount} ★\n"
        text += f"Сумма: {amount * 1.52:.2f} ₽\n\n"
        text += f"📱 **Номер:** {SBP_PHONE}\n"
        text += f"🏦 **Банк:** {SBP_BANK}\n"
        text += f"👤 **Получатель:** {SBP_NAME}\n\n"
        text += "❗ Счёт действителен 30 минут.\n"
        text += "После оплаты пришлите скриншот чека в этот чат."
        
        await query.edit_message_text(
            text,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ИГРЫ =====
    if data == "games":
        await query.edit_message_text(
            f"🎮 **Игры**\n\n"
            f"Выбери игру:",
            reply_markup=games_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("game_"):
        game = data.split("_")[1]
        await query.edit_message_text(
            f"🎯 **Игра: {game.capitalize()}**\n\n"
            f"Шанс победы: 30%\n\n"
            f"Выбери приз (ставка = 50% от приза):",
            reply_markup=game_prize_menu(game),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("prize_"):
        parts = data.split("_")
        game = parts[1]
        prize = int(parts[2])
        bet = int(parts[3])
        
        balance = get_bonus_balance(user_id)
        if balance < bet:
            await query.edit_message_text(
                f"❌ **Недостаточно звёзд!**\n\n"
                f"Нужно {bet} ★, у тебя {balance} ★.",
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
            return
        
        add_bonus_balance(user_id, -bet)
        
        if random.random() < 0.3:
            add_bonus_balance(user_id, prize)
            new_balance = get_bonus_balance(user_id)
            await query.edit_message_text(
                f"🎉 **ПОБЕДА!**\n\n"
                f"Ты выиграл {prize} ★ в {game.capitalize()}!\n"
                f"🎁 Новый баланс: {new_balance} ★",
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        else:
            new_balance = get_bonus_balance(user_id)
            await query.edit_message_text(
                f"😢 **ПРОИГРЫШ**\n\n"
                f"Ты проиграл {bet} ★ в {game.capitalize()}.\n"
                f"🎁 Новый баланс: {new_balance} ★",
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        return

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('withdraw_custom'):
        try:
            amount = int(text)
            if amount < 15:
                await update.message.reply_text("❌ Минимальная сумма — 15 ★.")
                return
            
            bonus = get_bonus_balance(user_id)
            if amount > bonus:
                await update.message.reply_text(f"❌ У тебя {bonus} ★, а нужно {amount} ★.")
                return
            
            create_withdrawal(user_id, amount)
            add_bonus_balance(user_id, -amount)
            
            await update.message.reply_text(
                f"✅ **Заявка на вывод создана!**\n\n"
                f"Сумма: {amount} ★\n\n"
                f"Администратор проверит заявку.",
                parse_mode="Markdown"
            )
            
            await context.bot.send_message(
                ADMIN_ID,
                f"📤 **НОВАЯ ЗАЯВКА НА ВЫВОД**\n\n"
                f"👤 Пользователь: @{update.effective_user.username or 'без юзернейма'}\n"
                f"🆔 ID: {user_id}\n"
                f"💰 Сумма: {amount} ★",
                parse_mode="Markdown"
            )
        except:
            await update.message.reply_text("❌ Введите число!")
        context.user_data['withdraw_custom'] = False
        return
    
    if update.message.photo:
        await update.message.reply_text(
            f"✅ **Чек получен!**\n\n"
            f"Администратор проверит оплату в ближайшее время.",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            ADMIN_ID,
            f"📤 **Новый чек** от @{update.effective_user.username or 'пользователя'}!",
            parse_mode="Markdown"
        )
        return

# ========== АДМИН-ПАНЕЛЬ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ **Доступ запрещён!**")
        return
    
    await update.message.reply_text(
        f"🔧 **Админ-панель**\n\n"
        f"Выбери раздел:",
        reply_markup=admin_menu(),
        parse_mode="Markdown"
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if user_id != ADMIN_ID:
        await query.edit_message_text(
            f"❌ **Доступ запрещён!**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data == "admin_orders":
        orders = get_pending_orders()
        if not orders:
            await query.edit_message_text(
                f"📭 **Заказов нет**",
                reply_markup=admin_menu(),
                parse_mode="Markdown"
            )
            return
        
        text = "📦 **АКТИВНЫЕ ЗАКАЗЫ**\n\n"
        for o in orders:
            order_id, uid, amount, date = o
            user = get_user(uid)
            username = user[1] if user else "Неизвестно"
            text += f"🆔 #{order_id} | @{username} | {amount} ★ | {date[:16]}\n"
            text += f"   ✅ `/confirm_order {order_id}`\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data == "admin_withdrawals":
        withdrawals = get_pending_withdrawals()
        if not withdrawals:
            await query.edit_message_text(
                f"📭 **Заявок нет**",
                reply_markup=admin_menu(),
                parse_mode="Markdown"
            )
            return
        
        text = "📤 **ЗАЯВКИ НА ВЫВОД**\n\n"
        for w in withdrawals:
            w_id, uid, amount, date = w
            user = get_user(uid)
            username = user[1] if user else "Неизвестно"
            text += f"🆔 #{w_id} | @{username} | {amount} ★ | {date[:16]}\n"
            text += f"   ✅ `/confirm_withdrawal {w_id}`\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data == "admin_stats":
        users, orders, pending, completed, total_bonus = get_stats()
        text = f"📊 **Статистика**\n\n"
        text += f"👥 Всего пользователей: {users}\n"
        text += f"📦 Всего заказов: {orders}\n"
        text += f"⏳ Ожидают оплаты: {pending} ★\n"
        text += f"✅ Выполнено: {completed} ★\n"
        text += f"🎁 Всего бонусных звёзд: {total_bonus} ★\n"
        
        await query.edit_message_text(
            text,
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return

async def confirm_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ **Доступ запрещён!**")
        return
    
    try:
        order_id = int(context.args[0])
        orders = get_pending_orders()
        
        order = None
        for o in orders:
            if o[0] == order_id:
                order = o
                break
        
        if not order:
            await update.message.reply_text("❌ **Заказ не найден!**")
            return
        
        order_id, user_id, amount, date = order
        
        success = await send_stars(context.bot, user_id, amount)
        
        if success:
            update_order_status(order_id, "completed")
            await update.message.reply_text(
                f"✅ **Заказ выполнен!**\n\n"
                f"Звёзды отправлены пользователю @{get_user(user_id)[1] or 'без юзернейма'}.\n"
                f"Сумма: {amount} ★",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ **Ошибка отправки!**\n\n"
                f"Не удалось отправить звёзды. Проверь настройки бота.",
                parse_mode="Markdown"
            )
    except:
        await update.message.reply_text(
            f"❌ **Ошибка**\n\nИспользуйте: `/confirm_order ID`",
            parse_mode="Markdown"
        )

async def confirm_withdrawal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ **Доступ запрещён!**")
        return
    
    try:
        w_id = int(context.args[0])
        withdrawals = get_pending_withdrawals()
        
        w = None
        for w_item in withdrawals:
            if w_item[0] == w_id:
                w = w_item
                break
        
        if not w:
            await update.message.reply_text("❌ **Заявка не найдена!**")
            return
        
        w_id, user_id, amount, date = w
        update_withdrawal_status(w_id, "completed")
        
        await context.bot.send_message(
            user_id,
            f"✅ **Звёзды выведены!**\n\n"
            f"Твоя заявка на вывод {amount} ★ подтверждена!\n"
            f"Звёзды отправлены на твой Telegram-аккаунт.",
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ **Вывод подтверждён!**\n\n"
            f"Пользователь @{get_user(user_id)[1] or 'без юзернейма'} получил уведомление.",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(
            f"❌ **Ошибка**\n\nИспользуйте: `/confirm_withdrawal ID`",
            parse_mode="Markdown"
        )

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("confirm_order", confirm_order_command))
    app.add_handler(CommandHandler("confirm_withdrawal", confirm_withdrawal_command))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, handle_message))
    
    print("🚀 Starsov Bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()