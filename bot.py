# -*- coding: utf-8 -*-
"""
Starsov Bot — покупка звёзд, Premium, Steam, игры, партнёрская программа
Все виды оплаты: СБП, TON, CryptoBot, USDT, BTC, ETH
Фичи: реферальный бонус (+3★), ежедневный бонус (серия 5 дней), челлендж (+5★)
лидерборд, история покупок, рассылка, подписка на канал, красивое оформление
"""

import os
import sqlite3
import json
import random
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from mystars_faas import MyStarsClient

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8683456508:AAGNc2bxpKgmI5bxbg3VE1iNcA5VxSt5WYQ"
ADMIN_ID = 5141751465
MYSTARS_API_KEY = "faas_e629a8b74663a0b4bd43fc2b4793a2397c13077cd0c57dac8533419551781bc5"
CHANNEL_USERNAME = "starsovoff"

SBP_NAME = "Салим Т."
SBP_BANK = "Сбербанк"
SBP_PHONE = "+7(939) 315-86-67"

WALLETS = {
    "ton": "UQC2uEHQN54xepxrkmdBswzF_EQvw7hwagYwRbVxVTxbUTyU",
    "usdt_trc20": "TKw8QZ2MM8zNHncLUejcMWLZLNFHfaKP1B",
    "btc": "bc1q04tgy8up0h2katr8l4v4a7wg05ajjxqx6d6lra",
    "eth": "0xB79c3b8C243EC56C7a73a60ADE3E3ecdCB267396"
}

client = MyStarsClient.production(MYSTARS_API_KEY)

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
            total_earned REAL DEFAULT 0.0,
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
            type TEXT,
            amount TEXT,
            payment_method TEXT,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS stars_balance (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

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
        add_stars_balance(user_id, 3)
    cur.execute('INSERT OR IGNORE INTO stars_balance (user_id, balance) VALUES (?, 0)', (user_id,))
    conn.commit()
    conn.close()

def add_stars_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE stars_balance SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_stars_balance(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT balance FROM stars_balance WHERE user_id = ?', (user_id,))
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

def get_referrer_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def create_order(user_id, order_type, amount, payment_method):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO orders (user_id, type, amount, payment_method, date) VALUES (?, ?, ?, ?, ?)',
                (user_id, order_type, amount, payment_method, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_orders(user_id, limit=10):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT id, type, amount, payment_method, status, date FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT ?', (user_id, limit))
    return cur.fetchall()

def get_leaderboard():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
        SELECT u.username, s.balance
        FROM users u
        JOIN stars_balance s ON u.user_id = s.user_id
        ORDER BY s.balance DESC LIMIT 10
    ''')
    return cur.fetchall()

def get_daily_streak(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT daily_streak, last_daily FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    if result:
        return result[0], result[1]
    return 0, None

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
    if result:
        return result[0], result[1]
    return 0, None

def update_challenge_progress(user_id, progress, completed_date):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE users SET challenge_progress = ?, challenge_completed = ? WHERE user_id = ?', (progress, completed_date, user_id))
    conn.commit()
    conn.close()

def create_withdrawal(user_id, amount, wallet):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO withdrawals (user_id, amount, wallet, date) VALUES (?, ?, ?, ?)',
                (user_id, amount, wallet, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT user_id FROM users')
    return [u[0] for u in cur.fetchall()]

# ========== ОФОРМЛЕНИЕ ==========
def format_message(title, body):
    return f"━━━━━━━━━━━━━━━━━━━\n🌟 **STARSOV**\n━━━━━━━━━━━━━━━━━━━\n{title}\n\n{body}\n━━━━━━━━━━━━━━━━━━━"

# ========== ПРОВЕРКА ПОДПИСКИ ==========
async def is_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

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
        [InlineKeyboardButton("👑 Телеграм Премиум", callback_data="buy_premium")],
        [InlineKeyboardButton("🎁 Пополнить Steam", callback_data="buy_steam")],
        [InlineKeyboardButton("🎮 Игры", callback_data="games")],
        [InlineKeyboardButton("👥 Партнерская Программа", callback_data="referral")],
        [InlineKeyboardButton("💰 Мой баланс", callback_data="my_balance")],
        [InlineKeyboardButton("🏆 Рейтинг", callback_data="leaderboard")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus")],
        [InlineKeyboardButton("🎯 Челлендж", callback_data="daily_challenge")]
    ])
    return markup

def stars_amount_menu(target_user=None):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("50 ⭐", callback_data=f"stars_50_{target_user or 'me'}")],
        [InlineKeyboardButton("100 ⭐", callback_data=f"stars_100_{target_user or 'me'}")],
        [InlineKeyboardButton("250 ⭐", callback_data=f"stars_250_{target_user or 'me'}")],
        [InlineKeyboardButton("500 ⭐", callback_data=f"stars_500_{target_user or 'me'}")],
        [InlineKeyboardButton("1000 ⭐", callback_data=f"stars_1000_{target_user or 'me'}")],
        [InlineKeyboardButton("5000 ⭐", callback_data=f"stars_5000_{target_user or 'me'}")],
        [InlineKeyboardButton("💬 Купить Другу", callback_data="buy_for_friend")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def payment_menu(order_type, amount, target_user=None):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 СБП (Рубли)", callback_data=f"pay_sbp_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🪙 TON (авто)", callback_data=f"pay_ton_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🤖 CryptoBot (авто)", callback_data=f"pay_cryptobot_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("💵 USDT (TRC20)", callback_data=f"pay_usdt_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("₿ BTC", callback_data=f"pay_btc_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🔷 ETH", callback_data=f"pay_eth_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def premium_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("3 Месяца", callback_data="premium_3")],
        [InlineKeyboardButton("6 Месяцев", callback_data="premium_6")],
        [InlineKeyboardButton("1 Год", callback_data="premium_12")],
        [InlineKeyboardButton("💬 Купить Другу", callback_data="premium_for_friend")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    return markup

def steam_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("5$", callback_data="steam_5")],
        [InlineKeyboardButton("10$", callback_data="steam_10")],
        [InlineKeyboardButton("25$", callback_data="steam_25")],
        [InlineKeyboardButton("50$", callback_data="steam_50")],
        [InlineKeyboardButton("100$", callback_data="steam_100")],
        [InlineKeyboardButton("💬 Купить Другу", callback_data="steam_for_friend")],
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
        [InlineKeyboardButton("15 ★", callback_data=f"prize_{game}_15")],
        [InlineKeyboardButton("25 ★", callback_data=f"prize_{game}_25")],
        [InlineKeyboardButton("50 ★", callback_data=f"prize_{game}_50")],
        [InlineKeyboardButton("100 ★", callback_data=f"prize_{game}_100")],
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
    
    await update.message.reply_text(
        format_message(
            "🌟 Добро пожаловать в Starsov!",
            "Здесь можно купить Telegram Stars, Premium, пополнить Steam.\n\n"
            "Доступные способы оплаты: СБП, TON, CryptoBot, USDT, BTC, ETH.\n\n"
            "📌 Реферальный бонус: +3 ★ при регистрации!\n"
            "📌 Ежедневный бонус: до +5 ★ в день!\n\n"
            "Выбери действие ниже:"
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
                format_message("❌ Подписка не найдена!", "Пожалуйста, подпишись на канал и нажми «Проверить подписку» снова."),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME}")],
                    [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")]
                ]),
                parse_mode="Markdown"
            )
        return
    
    # ===== МОЙ БАЛАНС =====
    if data == "my_balance":
        balance = get_stars_balance(user_id)
        ref_balance = get_ref_balance(user_id)
        ref_count = get_ref_count(user_id)
        streak, _ = get_daily_streak(user_id)
        await query.edit_message_text(
            format_message(
                "💰 Мой баланс",
                f"⭐ Звёзды: {balance}\n"
                f"👥 Рефералов: {ref_count}\n"
                f"👥 Реферальный баланс: {ref_balance} TON\n"
                f"📅 Серия бонусов: {streak} дней\n\n"
                f"📌 Реферальный бонус: +3★ за каждого друга!"
            ),
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
        add_stars_balance(user_id, bonus)
        set_daily_streak(user_id, streak, today)
        
        await query.edit_message_text(
            format_message(
                "🎁 Ежедневный бонус!",
                f"⭐ +{bonus} звёзд!\n"
                f"📅 Серия: {streak}/5 дней\n\n"
                f"💰 Новый баланс: {get_stars_balance(user_id)} ★"
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
                f"⭐ Награда: +{challenge['reward']} ★\n\n"
                f"👥 Приглашай друзей по своей реферальной ссылке!"
            ),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ЛИДЕРБОРД =====
    if data == "leaderboard":
        leaderboard = get_leaderboard()
        if not leaderboard:
            await query.edit_message_text(
                format_message("🏆 Рейтинг", "Пока нет игроков в рейтинге."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        text = "🏆 **Топ-10 по звёздам**\n\n"
        for i, (username, balance) in enumerate(leaderboard, 1):
            text += f"{i}. @{username or 'Аноним'} — {balance} ★\n"
        
        await query.edit_message_text(
            format_message("🏆 Рейтинг", text),
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ИСТОРИЯ =====
    if data == "history":
        orders = get_user_orders(user_id)
        if not orders:
            await query.edit_message_text(
                format_message("📜 История", "У тебя пока нет заказов."),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        text = "📜 **История заказов**\n\n"
        for o in orders[:5]:
            text += f"🆔 {o[0]} | {o[1]} | {o[2]} | {o[3]} | {o[4]}\n"
        
        await query.edit_message_text(
            format_message("📜 История", text),
            reply_markup=main_menu(),
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
    
    if data == "buy_for_friend":
        await query.edit_message_text(
            "💬 **Покупка для друга**\n\n"
            "Введите @username друга или отправьте его ID.",
            parse_mode="Markdown"
        )
        context.user_data['buy_for_friend'] = True
        return
    
    if data.startswith("stars_"):
        parts = data.split("_")
        amount = parts[1]
        target = parts[2] if len(parts) > 2 else "me"
        if target == "me":
            target = user_id
        else:
            target = int(target)
        
        await query.edit_message_text(
            format_message(
                f"⭐ Покупка {amount} звёзд",
                f"Покупка для: @{query.from_user.username or 'вас'}\n\n"
                "Выберите способ оплаты:"
            ),
            reply_markup=payment_menu("stars", amount, target),
            parse_mode="Markdown"
        )
        return
    
    # ===== ТЕЛЕГРАМ ПРЕМИУМ =====
    if data == "buy_premium":
        await query.edit_message_text(
            format_message("👑 Telegram Premium", "Выберите срок:"),
            reply_markup=premium_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("premium_"):
        months = data.split("_")[1]
        await query.edit_message_text(
            format_message(
                f"👑 Premium - {months} мес.",
                "Выберите способ оплаты:"
            ),
            reply_markup=payment_menu("premium", months),
            parse_mode="Markdown"
        )
        return
    
    # ===== STEAM =====
    if data == "buy_steam":
        await query.edit_message_text(
            format_message("🎁 Пополнить Steam", "Выберите сумму:"),
            reply_markup=steam_menu(),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("steam_"):
        amount = data.split("_")[1]
        await query.edit_message_text(
            format_message(
                f"🎁 Steam на {amount}$",
                "Выберите способ оплаты:"
            ),
            reply_markup=payment_menu("steam", amount),
            parse_mode="Markdown"
        )
        return
    
    # ===== ОПЛАТА =====
    if data.startswith("pay_"):
        parts = data.split("_")
        method = parts[1]
        order_type = parts[2]
        amount = parts[3]
        target = parts[4] if len(parts) > 4 else "me"
        
        create_order(user_id, f"{order_type}_{amount}", amount, method)
        amount_int = int(amount)
        
        if method == "sbp":
            price_rub = amount_int * 0.5
            text = f"🇷🇺 **Оплата по СБП**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {price_rub} ₽\n\n"
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
        
        if method in ["ton", "cryptobot"]:
            try:
                recipient = query.from_user.username or query.from_user.first_name
                if target != "me" and target != user_id:
                    recipient = str(target)
                
                check = client.check_recipient(recipient, type="stars")
                if not check.eligible:
                    await query.edit_message_text(
                        format_message("❌ Ошибка", f"Пользователь @{recipient} не может получить звёзды."),
                        reply_markup=main_menu(),
                        parse_mode="Markdown"
                    )
                    return
                
                quote = client.get_pricing(type="stars", quantity=amount_int, payment_currency="ton")
                order = client.create_order(
                    type="stars",
                    recipient=recipient,
                    quantity=amount_int,
                    payment_currency="ton"
                )
                
                text = f"🪙 **Оплата через {method.upper()}**\n\n"
                text += f"Заказ: {order_type} на {amount} звёзд\n"
                text += f"💰 **Сумма:** {order.payment.amount} TON\n"
                text += f"📤 **Адрес:** `{order.payment.pay_to_address}`\n"
                text += f"📝 **Комментарий:** `{order.payment.memo}`\n\n"
                text += "❗ Счёт действителен 30 минут.\n"
                text += "После оплаты звёзды зачислятся автоматически."
                
                async def check_payment():
                    try:
                        final_order = client.wait_for_order(order.id, timeout=1800)
                        if final_order.status == "delivered":
                            await context.bot.send_message(user_id, f"✅ {amount} звёзд зачислены @{recipient}!")
                            add_stars_balance(user_id, amount_int)
                            ref_id = get_referrer_id(user_id)
                            if ref_id:
                                update_ref_balance(ref_id, float(order.payment.amount) * 0.1)
                        else:
                            await context.bot.send_message(user_id, f"⚠️ Статус заказа: {final_order.status}")
                    except Exception as e:
                        await context.bot.send_message(ADMIN_ID, f"⚠️ Ошибка: {e}")
                
                asyncio.create_task(check_payment())
                
            except Exception as e:
                text = f"❌ Ошибка: {e}"
            
            await query.edit_message_text(
                format_message(f"🪙 Оплата через {method.upper()}", text),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if method == "usdt":
            text = f"💵 **Оплата USDT (TRC20)**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount_int * 0.015} USDT\n\n"
            text += f"📍 **Адрес:**\n`{WALLETS['usdt_trc20']}`\n\n"
            text += "❗ Сеть: TRC20\n"
            text += "❗ Счёт действителен 30 минут.\n"
            text += "После оплаты пришлите скриншот чека в этот чат."
            await query.edit_message_text(
                format_message("💵 Оплата USDT", text),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if method == "btc":
            text = f"₿ **Оплата Bitcoin**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount_int * 0.0005} BTC\n\n"
            text += f"📍 **Адрес:**\n`{WALLETS['btc']}`\n\n"
            text += "❗ Счёт действителен 30 минут.\n"
            text += "После оплаты пришлите скриншот чека в этот чат."
            await query.edit_message_text(
                format_message("₿ Оплата Bitcoin", text),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
        
        if method == "eth":
            text = f"🔷 **Оплата Ethereum**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount_int * 0.008} ETH\n\n"
            text += f"📍 **Адрес:**\n`{WALLETS['eth']}`\n\n"
            text += "❗ Счёт действителен 30 минут.\n"
            text += "После оплаты пришлите скриншот чека в этот чат."
            await query.edit_message_text(
                format_message("🔷 Оплата Ethereum", text),
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
            return
    
    # ===== ПАРТНЁРСКАЯ ПРОГРАММА =====
    if data == "referral":
        ref_count = get_ref_count(user_id)
        ref_balance = get_ref_balance(user_id)
        ref_link = f"https://t.me/{context.bot.username}?start=r{user_id}"
        
        text = "👥 **Партнерская программа**\n\n"
        text += "Приглашайте людей и получайте 10% от нашего дохода НАВСЕГДА!\n\n"
        text += f"**Ссылка:** `{ref_link}`\n\n"
        text += f"Рефералов: {ref_count}\n"
        text += f"Баланс: {ref_balance} TON\n\n"
        text += "📌 За каждого приглашённого — +3★ новому пользователю!\n"
        text += "Минимальная выплата — 0.5 TON"
        
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Вывести", callback_data="withdraw_ref")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ])
        
        await query.edit_message_text(
            format_message("👥 Партнёрская программа", text),
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    if data == "withdraw_ref":
        await query.edit_message_text(
            format_message("💳 Вывод", "Формат: `0.5 UQB...`"),
            parse_mode="Markdown"
        )
        context.user_data['withdraw'] = True
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
                f"Шанс успеха: 40%\n\n"
                "Выбери приз:"
            ),
            reply_markup=game_prize_menu(game),
            parse_mode="Markdown"
        )
        return
    
    if data.startswith("prize_"):
        parts = data.split("_")
        game = parts[1]
        prize = int(parts[2])
        
        if random.random() < 0.4:
            add_stars_balance(user_id, prize)
            ref_id = get_referrer_id(user_id)
            if ref_id:
                update_ref_balance(ref_id, prize * 0.01)
            await query.edit_message_text(
                format_message(
                    "🎉 Поздравляем!",
                    f"+{prize} ★ в {game.capitalize()}!"
                ),
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                format_message("😢 Не повезло!", "Попробуй ещё раз."),
                reply_markup=games_menu(),
                parse_mode="Markdown"
            )
        return

# ========== ОБРАБОТЧИК СООБЩЕНИЙ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('withdraw'):
        try:
            parts = text.split()
            amount = float(parts[0])
            wallet = parts[1] if len(parts) > 1 else ""
            if amount >= 0.5:
                create_withdrawal(user_id, amount, wallet)
                await update.message.reply_text(
                    format_message("✅ Заявка создана!", "Ожидайте обработки."),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    format_message("❌ Ошибка", "Минимальная сумма вывода — 0.5 TON."),
                    parse_mode="Markdown"
                )
        except:
            await update.message.reply_text(
                format_message("❌ Ошибка", "Формат: `0.5 UQB...`"),
                parse_mode="Markdown"
            )
        context.user_data['withdraw'] = False
        return
    
    if context.user_data.get('buy_for_friend'):
        context.user_data['buy_for_friend'] = False
        await update.message.reply_text(
            format_message("💬 Покупка для друга", "Выберите количество звёзд:"),
            reply_markup=stars_amount_menu(),
            parse_mode="Markdown"
        )
        return
    
    if update.message.photo:
        await update.message.reply_text(
            format_message("✅ Чек получен!", "Администратор проверит оплату в ближайшее время."),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            ADMIN_ID,
            f"📤 Новый чек от @{update.effective_user.username or 'пользователя'}!"
        )
        return

# ========== АДМИН-КОМАНДЫ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            format_message("❌ Доступ запрещён!", "Эта команда только для админа."),
            parse_mode="Markdown"
        )
        return
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM users')
    users_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM orders')
    orders_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE date >= date('now', '-1 day')")
    today_orders = cur.fetchone()[0]
    cur.execute("SELECT SUM(amount) FROM orders")
    total_orders_ton = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE date >= date('now', '-7 day')")
    active_users = cur.fetchone()[0]
    conn.close()
    
    text = f"📊 **Расширенная статистика**\n\n"
    text += f"👥 Всего пользователей: {users_count}\n"
    text += f"📦 Заказов сегодня: {today_orders}\n"
    text += f"💰 Общая сумма покупок: {total_orders_ton} TON\n"
    text += f"🔥 Активных за неделю: {active_users}"
    
    await update.message.reply_text(
        format_message("📊 Статистика", text),
        parse_mode="Markdown"
    )

async def add_stars_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            format_message("❌ Доступ запрещён!", "Эта команда только для админа."),
            parse_mode="Markdown"
        )
        return
    
    try:
        username = context.args[0].replace("@", "")
        amount = int(context.args[1])
        
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        result = cur.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text(
                format_message("❌ Ошибка", f"Пользователь @{username} не найден!"),
                parse_mode="Markdown"
            )
            return
        
        add_stars_balance(result[0], amount)
        await update.message.reply_text(
            format_message("✅ Звёзды зачислены!", f"{amount} ★ зачислены @{username}!"),
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(
            format_message("❌ Ошибка", "Используйте: `/add_stars @username количество`"),
            parse_mode="Markdown"
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            format_message("❌ Доступ запрещён!", "Эта команда только для админа."),
            parse_mode="Markdown"
        )
        return
    
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            format_message("❌ Ошибка", "Используйте: `/broadcast Текст для рассылки`"),
            parse_mode="Markdown"
        )
        return
    
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, format_message("📢 РАССЫЛКА STARSOV", text), parse_mode="Markdown")
            sent += 1
        except:
            pass
    
    await update.message.reply_text(
        format_message("✅ Рассылка отправлена!", f"Отправлено {sent} пользователям."),
        parse_mode="Markdown"
    )

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("add_stars", add_stars_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, handle_message))
    
    print("🚀 Starsov Bot с ВСЕМИ фичами запущен!")
    print(f"📢 Канал: @{CHANNEL_USERNAME}")
    app.run_polling()

if __name__ == "__main__":
    main()