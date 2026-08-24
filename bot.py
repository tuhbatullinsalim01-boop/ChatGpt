# -*- coding: utf-8 -*-
"""
Starsov Bot — автоматическая отправка звёзд через Telegram API
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
TOKEN = "8923501366:AAGiQqZ1anGUJPndMtwj_AKbuKedFsKVu-8"
ADMIN_ID = 5141751465
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
            challenge_completed TEXT
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
        INSERT OR IGNORE INTO users (user_id, username, ref_code, referrer_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, ref_code, referrer_id))
    
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

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return True

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")]
        ])
        await update.message.reply_text(
            format_message("🌟 Добро пожаловать!", "Чтобы пользоваться ботом, подпишись на наш канал:"),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return False
    return True

# ========== КНОПКИ ==========
def main_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить Звезды", callback_data="buy_stars")],
        [InlineKeyboardButton("🎮 Игры", callback_data="games")],
        [InlineKeyboardButton("👥 Партнерская Программа", callback_data="referral")],
        [InlineKeyboardButton("💰 Мой баланс", callback_data="my_balance")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("🎯 Челлендж", callback_data="daily_challenge")],
        [InlineKeyboardButton("💸 Вывести бонусные ★", callback_data="withdraw_bonus")],
    ])
    return markup

def stars_amount_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("50 ⭐ — 76 ₽", callback_data="stars_50")],
        [InlineKeyboardButton("100 ⭐ — 152 ₽", callback_data="stars_100")],
        [InlineKeyboardButton("250 ⭐ — 380 ₽", callback_data="stars_250")],
        [InlineKeyboardButton("500 ⭐ — 760 ₽", callback_data="stars_500")],
        [InlineKeyboardButton("1000 ⭐ — 1 520 ₽", callback_data="stars_1000")],
        [InlineKeyboardButton("5000 ⭐ — 7 600 ₽", callback_data="stars_5000")],
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
        [InlineKeyboardButton("5 ★", callback_data="withdraw_5")],
        [InlineKeyboardButton("10 ★", callback_data="withdraw_10")],
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
    if not await check_subscription(update, context):
        return
    
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
    
    bonus = get_bonus_balance(user_id)
    await update.message.reply_text(
        format_message(
            "🌟 Добро пожаловать в Starsov!",
            f"🎁 Бонусный баланс: {bonus} ★\n\n"
            "Здесь можно купить Telegram Stars.\n"
            "Бонусные звёзды можно вывести!\n\n"
            "📌 Реферальный бонус: +3 ★ при регистрации!\n"
            "📌 Ежедневный бонус: до +5 ★ в день!\n\n"
            "Выбери действие:"
        ),
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "back":
        await query.edit_message_text(
            format_message("🌟 Главное меню:", "Выбери действие:"),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data == "check_sub":
        if await is_subscribed(user_id, context):
            await query.edit_message_text(
                format_message("✅ Подписка подтверждена!", "Теперь ты можешь пользоваться ботом."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                format_message("❌ Подписка не найдена!", "Подпишись и нажми снова."),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME}")],
                    [InlineKeyboardButton("✅ Проверить", callback_data="check_sub")]
                ]),
                parse_mode="Markdown"
            )
        return
    
    # ===== МОЙ БАЛАНС =====
    if data == "my_balance":
        bonus = get_bonus_balance(user_id)
        ref_balance = get_ref_balance(user_id)
        ref_count = get_ref_count(user_id)
        streak, _ = get_daily_streak(user_id)
        await query.edit_message_text(
            format_message(
                "💰 Мой баланс",
                f"🎁 Бонусные: {bonus} ★\n"
                f"👥 Рефералов: {ref_count}\n"
                f"👥 Реферальный баланс: {ref_balance} TON\n"
                f"📅 Серия бонусов: {streak} дней"
            ),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ВЫВОД БОНУСНЫХ ЗВЁЗД =====
    if data == "withdraw_bonus":
        bonus = get_bonus_balance(user_id)
        await query.edit_message_text(
            format_message(
                "💸 Вывод бонусных звёзд",
                f"🎁 Доступно для вывода: {bonus} ★\n\n"
                "Минимальная сумма вывода — 5 ★\n"
                "Выбери сумму:"
            ),
            reply_markup=withdrawal_amount_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("withdraw_"):
        parts = data.split("_")
        if parts[1] == "custom":
            await query.edit_message_text(
                format_message("💸 Введите сумму", "Введите количество звёзд для вывода (минимум 5):"),
                parse_mode="Markdown"
            )
            context.user_data['withdraw_custom'] = True
            return
        
        amount = int(parts[1])
        bonus = get_bonus_balance(user_id)
        
        if amount < 5:
            await query.edit_message_text(
                format_message("❌ Ошибка", "Минимальная сумма вывода — 5 ★."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if amount > bonus:
            await query.edit_message_text(
                format_message("❌ Недостаточно звёзд!", f"У тебя {bonus} ★, а нужно {amount} ★."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        create_withdrawal(user_id, amount)
        add_bonus_balance(user_id, -amount)
        
        await query.edit_message_text(
            format_message(
                "✅ Заявка на вывод создана!",
                f"Сумма: {amount} ★\n\n"
                "Администратор проверит заявку."
            ),
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
    
    # ===== ПОКУПКА ЗВЁЗД =====
    if data == "buy_stars":
        await query.edit_message_text(
            format_message("⭐ Купить Звезды", "Выберите количество:"),
            reply_markup=stars_amount_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("stars_"):
        amount = int(data.split("_")[1])
        price_rub = amount * 1.52
        await query.edit_message_text(
            format_message(
                f"⭐ Покупка {amount} ★",
                f"💳 Стоимость: {price_rub:.2f} ₽\n\n"
                "Выберите способ оплаты:"
            ),
            reply_markup=payment_menu("stars", amount),
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
            format_message("🇷🇺 Оплата по СБП", text),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ИГРЫ =====
    if data == "games":
        await query.edit_message_text(
            format_message("🎮 Игры", "Выбери игру:"),
            reply_markup=games_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("game_"):
        game = data.split("_")[1]
        await query.edit_message_text(
            format_message(
                f"🎯 Игра: {game.capitalize()}",
                f"Шанс победы: 30%\n\n"
                "Выбери приз (ставка = 50% от приза):"
            ),
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
                format_message("❌ Недостаточно звёзд!", f"Нужно {bet} ★, у тебя {balance} ★."),
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
            return
        
        add_bonus_balance(user_id, -bet)
        
        if random.random() < 0.3:
            add_bonus_balance(user_id, prize)
            new_balance = get_bonus_balance(user_id)
            await query.edit_message_text(
                format_message(
                    f"🎉 ПОБЕДА!",
                    f"Ты выиграл {prize} ★ в {game.capitalize()}!\n"
                    f"🎁 Новый бонусный баланс: {new_balance} ★"
                ),
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        else:
            new_balance = get_bonus_balance(user_id)
            await query.edit_message_text(
                format_message(
                    f"😢 ПРОИГРЫШ",
                    f"Ты проиграл {bet} ★ в {game.capitalize()}.\n"
                    f"🎁 Новый бонусный баланс: {new_balance} ★"
                ),
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        return
    
    # ===== РЕФЕРАЛЫ =====
    if data == "referral":
        ref_count = get_ref_count(user_id)
        ref_balance = get_ref_balance(user_id)
        ref_link = f"https://t.me/{context.bot.username}?start=r{user_id}"
        
        text = "👥 **Партнерская программа**\n\n"
        text += "Приглашайте людей и получайте 10% от нашего дохода НАВСЕГДА!\n\n"
        text += f"**Ссылка:** `{ref_link}`\n\n"
        text += f"Рефералов: {ref_count}\n"
        text += f"Баланс: {ref_balance} TON"
        
        await query.edit_message_text(
            format_message("👥 Партнёрская программа", text),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ЕЖЕДНЕВНЫЙ БОНУС =====
    if data == "daily_bonus":
        today = datetime.now().date().isoformat()
        streak, last_daily = get_daily_streak(user_id)
        
        if last_daily == today:
            await query.edit_message_text(
                format_message("❌ Бонус получен!", "Ты уже получил бонус сегодня."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if last_daily:
            last_date = datetime.strptime(last_daily, "%Y-%m-%d").date()
            delta = (datetime.now().date() - last_date).days
            if delta == 1:
                streak = min(streak + 1, 5)
            else:
                streak = 1
        else:
            streak = 1
        
        bonus = streak
        add_bonus_balance(user_id, bonus)
        set_daily_streak(user_id, streak, today)
        
        new_balance = get_bonus_balance(user_id)
        await query.edit_message_text(
            format_message(
                "🎁 Ежедневный бонус!",
                f"⭐ +{bonus} ★ (бонусные)!\n"
                f"📅 Серия: {streak}/5 дней\n\n"
                f"🎁 Новый бонусный баланс: {new_balance} ★"
            ),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ЧЕЛЛЕНДЖ =====
    if data == "daily_challenge":
        progress, completed = get_challenge_progress(user_id)
        today = datetime.now().date().isoformat()
        
        if completed == today:
            await query.edit_message_text(
                format_message("✅ Челлендж выполнен!", "Ты уже получил награду сегодня."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        challenges = [
            {"desc": "Пригласи 1 друга", "target": 1, "reward": 1},
            {"desc": "Пригласи 2 друзей", "target": 2, "reward": 2},
            {"desc": "Пригласи 3 друзей", "target": 3, "reward": 3},
            {"desc": "Пригласи 4 друзей", "target": 4, "reward": 4},
            {"desc": "Пригласи 5 друзей", "target": 5, "reward": 5},
        ]
        challenge = random.choice(challenges)
        
        await query.edit_message_text(
            format_message(
                "🎯 Ежедневный челлендж!",
                f"📌 Задание: {challenge['desc']}\n"
                f"📊 Прогресс: {progress}/{challenge['target']}\n"
                f"⭐ Награда: +{challenge['reward']} ★ (бонусные)"
            ),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return

# ========== АДМИН-ПАНЕЛЬ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            format_message("❌ Доступ запрещён!", "Эта команда только для админа."),
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        format_message("🔧 Админ-панель", "Выбери раздел:"),
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
            format_message("❌ Доступ запрещён!", "Эта команда только для админа."),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ЗАКАЗЫ =====
    if data == "admin_orders":
        orders = get_pending_orders()
        if not orders:
            await query.edit_message_text(
                format_message("📭 Заказов нет", "Нет активных заказов."),
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
            format_message("📦 Заказы", text),
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ВЫВОДЫ =====
    if data == "admin_withdrawals":
        withdrawals = get_pending_withdrawals()
        if not withdrawals:
            await query.edit_message_text(
                format_message("📭 Заявок нет", "Нет активных заявок на вывод."),
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
            format_message("📤 Заявки на вывод", text),
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== СТАТИСТИКА =====
    if data == "admin_stats":
        users, orders, pending, completed, total_bonus = get_stats()
        text = f"📊 **Статистика**\n\n"
        text += f"👥 Всего пользователей: {users}\n"
        text += f"📦 Всего заказов: {orders}\n"
        text += f"⏳ Ожидают оплаты: {pending} ★\n"
        text += f"✅ Выполнено: {completed} ★\n"
        text += f"🎁 Всего бонусных звёзд: {total_bonus} ★\n"
        
        await query.edit_message_text(
            format_message("📊 Статистика", text),
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return

# ========== АДМИН-КОМАНДЫ ==========
async def confirm_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён!")
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
            await update.message.reply_text("❌ Заказ не найден!")
            return
        
        order_id, user_id, amount, date = order
        
        # Отправляем звёзды через API
        success = await send_stars(context.bot, user_id, amount)
        
        if success:
            update_order_status(order_id, "completed")
            await update.message.reply_text(
                format_message(
                    "✅ Заказ выполнен!",
                    f"Звёзды отправлены пользователю @{get_user(user_id)[1] or 'без юзернейма'}.\n"
                    f"Сумма: {amount} ★"
                ),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                format_message(
                    "❌ Ошибка отправки!",
                    "Не удалось отправить звёзды. Проверь настройки бота."
                ),
                parse_mode="Markdown"
            )
    except:
        await update.message.reply_text(
            format_message("❌ Ошибка", "Используйте: `/confirm_order ID`"),
            parse_mode="Markdown"
        )

async def confirm_withdrawal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён!")
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
            await update.message.reply_text("❌ Заявка не найдена!")
            return
        
        w_id, user_id, amount, date = w
        update_withdrawal_status(w_id, "completed")
        
        await context.bot.send_message(
            user_id,
            format_message(
                "✅ Звёзды выведены!",
                f"Твоя заявка на вывод {amount} ★ подтверждена!\n"
                f"Звёзды отправлены на твой Telegram-аккаунт."
            ),
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            format_message(
                "✅ Вывод подтверждён!",
                f"Пользователь @{get_user(user_id)[1] or 'без юзернейма'} получил уведомление."
            ),
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(
            format_message("❌ Ошибка", "Используйте: `/confirm_withdrawal ID`"),
            parse_mode="Markdown"
        )

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('withdraw_custom'):
        try:
            amount = int(text)
            if amount < 5:
                await update.message.reply_text("❌ Минимальная сумма вывода — 5 ★.")
                return
            
            bonus = get_bonus_balance(user_id)
            if amount > bonus:
                await update.message.reply_text(f"❌ У тебя {bonus} ★, а нужно {amount} ★.")
                return
            
            create_withdrawal(user_id, amount)
            add_bonus_balance(user_id, -amount)
            
            await update.message.reply_text(
                format_message(
                    "✅ Заявка на вывод создана!",
                    f"Сумма: {amount} ★\n\n"
                    "Администратор проверит заявку."
                ),
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
            format_message("✅ Чек получен!", "Администратор проверит оплату в ближайшее время."),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            ADMIN_ID,
            f"📤 Новый чек от @{update.effective_user.username or 'пользователя'}!",
            parse_mode="Markdown"
        )
        return

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
    
    print("🚀 Starsov Bot (авто-отправка звёзд) запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()