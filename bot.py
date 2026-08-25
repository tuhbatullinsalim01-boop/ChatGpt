# -*- coding: utf-8 -*-
"""
Starsov — Telegram-бот заявок на Stars, Premium и баланс.
"""

import os
import sqlite3
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8845418318:AAFwMTgSYOCWj3mSyzDhobO53O1xdo_tDQY"
ADMIN_ID = 5141751465
SUPPORT_USERNAME = "mirrey5"
CHANNEL_USERNAME = "starsovoff"

SBP_NAME = "Салим Т."
SBP_BANK = "Сбербанк"
SBP_PHONE = "+7(939) 315-86-67"

DB_NAME = "starsov.db"

# Цены
STAR_PRICES = {
    15: 23,
    50: 76,
    100: 152,
    250: 380,
    500: 760,
    1000: 1520,
    5000: 7600,
}
PREMIUM_PRICES = {
    3: {"rub": 989, "stars": 1000},
    6: {"rub": 1219, "stars": 1500},
    12: {"rub": 2130, "stars": 2500},
}
STAR_PRICE_PER_ONE = 1.52

logging.basicConfig(level=logging.INFO)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            reg_date TEXT,
            rub_balance REAL DEFAULT 0,
            stars_balance INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            rub_amount REAL,
            status TEXT DEFAULT 'pending',
            date TEXT,
            receipt_file_id TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sell_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            stars_count INTEGER,
            rub_total REAL,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            date TEXT,
            receipt_file_id TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            date TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS premium_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            months INTEGER,
            rub_amount REAL,
            stars_cost INTEGER,
            status TEXT DEFAULT 'pending',
            date TEXT,
            receipt_file_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO users (user_id, username, reg_date)
        VALUES (?, ?, ?)
    ''', (user_id, username, datetime.now().strftime('%d.%m.%Y %H:%M')))
    conn.commit()
    conn.close()

def update_balance(user_id, rub_amount=0, stars_amount=0):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if rub_amount:
        c.execute('UPDATE users SET rub_balance = rub_balance + ? WHERE user_id = ?', (rub_amount, user_id))
    if stars_amount:
        c.execute('UPDATE users SET stars_balance = stars_balance + ? WHERE user_id = ?', (stars_amount, user_id))
    conn.commit()
    conn.close()

def create_order(user_id, amount, rub_amount, receipt_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO orders (user_id, amount, rub_amount, date, receipt_file_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, amount, rub_amount, datetime.now().isoformat(), receipt_file_id))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def create_sell_request(user_id, stars_count, rub_total):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO sell_requests (user_id, stars_count, rub_total, date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, stars_count, rub_total, datetime.now().isoformat()))
    req_id = c.lastrowid
    conn.commit()
    conn.close()
    return req_id

def create_deposit(user_id, amount, receipt_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO deposits (user_id, amount, date, receipt_file_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, amount, datetime.now().isoformat(), receipt_file_id))
    dep_id = c.lastrowid
    conn.commit()
    conn.close()
    return dep_id

def create_withdrawal(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO withdrawals (user_id, amount, date)
        VALUES (?, ?, ?)
    ''', (user_id, amount, datetime.now().isoformat()))
    w_id = c.lastrowid
    conn.commit()
    conn.close()
    return w_id

def create_premium_order(user_id, months, rub_amount, stars_cost, receipt_file_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO premium_orders (user_id, months, rub_amount, stars_cost, date, receipt_file_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, months, rub_amount, stars_cost, datetime.now().isoformat(), receipt_file_id))
    p_id = c.lastrowid
    conn.commit()
    conn.close()
    return p_id

def get_pending_orders():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE status = "pending" OR status = "receipt_sent" ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_sell_requests():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM sell_requests WHERE status = "pending" ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_deposits():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM deposits WHERE status = "receipt_sent" ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM withdrawals WHERE status = "pending" ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_premium():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM premium_orders WHERE status = "receipt_sent" ORDER BY id ASC')
    rows = c.fetchall()
    conn.close()
    return rows

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def update_sell_request_status(req_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE sell_requests SET status = ? WHERE id = ?', (status, req_id))
    conn.commit()
    conn.close()

def update_deposit_status(dep_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE deposits SET status = ? WHERE id = ?', (status, dep_id))
    conn.commit()
    conn.close()

def update_withdrawal_status(w_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (status, w_id))
    conn.commit()
    conn.close()

def update_premium_status(p_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('UPDATE premium_orders SET status = ? WHERE id = ?', (status, p_id))
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_sell_request(req_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM sell_requests WHERE id = ?', (req_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_deposit(dep_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM deposits WHERE id = ?', (dep_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_withdrawal(w_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM withdrawals WHERE id = ?', (w_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_premium_order(p_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT * FROM premium_orders WHERE id = ?', (p_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM orders')
    orders = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM orders WHERE status = "completed"')
    completed = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = "completed"')
    stars_sold = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(rub_amount), 0) FROM orders WHERE status = "completed"')
    rub_earned = c.fetchone()[0]
    conn.close()
    return users, orders, completed, stars_sold, rub_earned

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить звёзды", callback_data="buy"),
         InlineKeyboardButton("📤 Продать звёзды", callback_data="sell")],
        [InlineKeyboardButton("👑 Telegram Premium", callback_data="premium"),
         InlineKeyboardButton("💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"),
         InlineKeyboardButton("📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton("ℹ️ Информация", callback_data="info"),
         InlineKeyboardButton("📊 Калькулятор", callback_data="calculator")],
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("‹ Назад", callback_data="back")]])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Заказы Stars", callback_data="admin_orders"),
         InlineKeyboardButton("📤 Продажа Stars", callback_data="admin_sell")],
        [InlineKeyboardButton("💰 Пополнения", callback_data="admin_deposits"),
         InlineKeyboardButton("👑 Premium", callback_data="admin_premium")],
        [InlineKeyboardButton("💸 Выводы", callback_data="admin_withdrawals"),
         InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ])

def decision_buttons(kind, order_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{kind}_{order_id}"),
         InlineKeyboardButton("❌ Отказать", callback_data=f"reject_{kind}_{order_id}")]
    ])

def stars_packages():
    buttons = []
    for stars, rub in STAR_PRICES.items():
        buttons.append([InlineKeyboardButton(f"{stars} ★ — {rub} ₽", callback_data=f"buy_pack_{stars}")])
    buttons.append([InlineKeyboardButton("‹ Назад", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

def premium_packages():
    buttons = []
    for months, data in PREMIUM_PRICES.items():
        buttons.append([InlineKeyboardButton(f"{months} мес. — {data['rub']} ₽", callback_data=f"premium_pack_{months}")])
    buttons.append([InlineKeyboardButton("‹ Назад", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

def sell_amounts():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("15 ★", callback_data="sell_15"),
         InlineKeyboardButton("20 ★", callback_data="sell_20"),
         InlineKeyboardButton("50 ★", callback_data="sell_50")],
        [InlineKeyboardButton("100 ★", callback_data="sell_100"),
         InlineKeyboardButton("Своя сумма", callback_data="sell_custom")],
        [InlineKeyboardButton("‹ Назад", callback_data="back")],
    ])

def withdraw_amounts():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("100 ₽", callback_data="withdraw_100"),
         InlineKeyboardButton("500 ₽", callback_data="withdraw_500"),
         InlineKeyboardButton("1000 ₽", callback_data="withdraw_1000")],
        [InlineKeyboardButton("Своя сумма", callback_data="withdraw_custom")],
        [InlineKeyboardButton("‹ Назад", callback_data="back")],
    ])

# ========== ФУНКЦИИ ==========
def fmt_rub(amount):
    return f"{amount:,.0f}".replace(",", " ") + " ₽"

def is_admin(user_id):
    return user_id == ADMIN_ID

# ========== ОБРАБОТЧИКИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username or "")
    
    text = (
        "*Добро пожаловать в Starsov!*\n\n"
        "Здесь можно купить и продать Telegram Stars, оформить Premium.\n\n"
        f"💰 Текущий баланс: *{fmt_rub(get_user(user.id)[3] or 0)}*\n\n"
        "Выберите действие:"
    )
    await update.message.reply_text(text, reply_markup=main_menu())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "back":
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=main_menu()
        )
        return
    
    # ===== ПОКУПКА =====
    if data == "buy":
        await query.edit_message_text(
            "Выберите пакет Stars:",
            reply_markup=stars_packages()
        )
        return
    
    if data.startswith("buy_pack_"):
        stars = int(data.split("_")[2])
        rub = STAR_PRICES[stars]
        context.user_data['pending_buy'] = {'stars': stars, 'rub': rub}
        
        await query.edit_message_text(
            f"⭐ {stars} ★ — *{fmt_rub(rub)}*\n\n"
            "Способ оплаты:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 СБП (чек)", callback_data="buy_sbp")],
                [InlineKeyboardButton("💰 С баланса", callback_data="buy_balance")],
                [InlineKeyboardButton("‹ Назад", callback_data="buy")],
            ])
        )
        return
    
    if data == "buy_sbp":
        pending = context.user_data.get('pending_buy')
        if not pending:
            await query.edit_message_text("Сессия истекла. Выберите пакет заново.", reply_markup=main_menu())
            return
        
        order_id = create_order(user_id, pending['stars'], pending['rub'])
        context.user_data['flow'] = f"order_receipt_{order_id}"
        
        text = (
            f"*Оплата по СБП*\n\n"
            f"Сумма: *{fmt_rub(pending['rub'])}*\n"
            f"Получатель: *{SBP_NAME}*\n"
            f"Банк: *{SBP_BANK}*\n"
            f"Номер: `{SBP_PHONE}`\n\n"
            "После перевода отправьте скриншот чека в этот чат."
        )
        await query.edit_message_text(text, reply_markup=back_menu())
        return
    
    if data == "buy_balance":
        pending = context.user_data.get('pending_buy')
        if not pending:
            await query.edit_message_text("Сессия истекла.", reply_markup=main_menu())
            return
        
        user = get_user(user_id)
        if user[3] < pending['rub']:
            await query.edit_message_text(
                f"Недостаточно средств. Доступно: *{fmt_rub(user[3])}*",
                reply_markup=main_menu()
            )
            return
        
        order_id = create_order(user_id, pending['stars'], pending['rub'])
        update_balance(user_id, rub_amount=-pending['rub'])
        update_order_status(order_id, "completed")
        
        await query.edit_message_text(
            f"✅ Оплачено с баланса.\n"
            f"Заявка *#{order_id}* создана. Администратор выдаст Stars вручную.",
            reply_markup=main_menu()
        )
        await notify_admin(f"📦 Заказ #{order_id} оплачен с баланса\nПользователь: @{query.from_user.username or user_id}\nStars: {pending['stars']} ★")
        return
    
    # ===== ПРОДАЖА =====
    if data == "sell":
        await query.edit_message_text(
            "*Продажа Stars*\n\n"
            "Выберите количество Stars для продажи.\n"
            "Цену установит администратор.\n\n"
            "После создания заявки дождитесь подтверждения.",
            reply_markup=sell_amounts()
        )
        return
    
    if data.startswith("sell_"):
        if data == "sell_custom":
            context.user_data['flow'] = "sell_custom"
            await query.edit_message_text(
                "Введите количество Stars (минимум 15):",
                reply_markup=back_menu()
            )
            return
        
        stars = int(data.split("_")[1])
        req_id = create_sell_request(user_id, stars, 0)
        await notify_admin(f"📤 Заявка на продажу #{req_id}\nПользователь: @{query.from_user.username or user_id}\nStars: {stars} ★")
        
        await query.edit_message_text(
            f"✅ Заявка *#{req_id}* создана.\n"
            f"Stars: {stars} ★\n\n"
            "Администратор рассмотрит заявку и предложит цену.",
            reply_markup=main_menu()
        )
        return
    
    # ===== PREMIUM =====
    if data == "premium":
        await query.edit_message_text(
            "*Telegram Premium*\n\n"
            "Выберите срок:",
            reply_markup=premium_packages()
        )
        return
    
    if data.startswith("premium_pack_"):
        months = int(data.split("_")[2])
        rub = PREMIUM_PRICES[months]['rub']
        stars_cost = PREMIUM_PRICES[months]['stars']
        
        order_id = create_premium_order(user_id, months, rub, stars_cost)
        context.user_data['flow'] = f"premium_receipt_{order_id}"
        
        text = (
            f"*Telegram Premium — {months} мес.*\n"
            f"Сумма: *{fmt_rub(rub)}*\n\n"
            f"Получатель: *{SBP_NAME}*\n"
            f"Банк: *{SBP_BANK}*\n"
            f"Номер: `{SBP_PHONE}`\n\n"
            "После перевода отправьте скриншот чека."
        )
        await query.edit_message_text(text, reply_markup=back_menu())
        return
    
    # ===== ПОПОЛНЕНИЕ =====
    if data == "deposit":
        await query.edit_message_text(
            "*Пополнение баланса*\n\n"
            "Переведите деньги по реквизитам СБП и отправьте чек.\n\n"
            f"Получатель: *{SBP_NAME}*\n"
            f"Банк: *{SBP_BANK}*\n"
            f"Номер: `{SBP_PHONE}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Я перевел(а), отправить чек", callback_data="deposit_sbp")],
                [InlineKeyboardButton("‹ Назад", callback_data="back")],
            ])
        )
        return
    
    if data == "deposit_sbp":
        context.user_data['flow'] = "deposit_receipt"
        await query.edit_message_text(
            "Отправьте скриншот чека в этот чат.",
            reply_markup=back_menu()
        )
        return
    
    # ===== ПРОФИЛЬ =====
    if data == "profile":
        user = get_user(user_id)
        if not user:
            await query.edit_message_text("Пользователь не найден.", reply_markup=main_menu())
            return
        
        text = (
            f"*👤 Профиль*\n\n"
            f"ID: `{user[0]}`\n"
            f"Username: @{user[1] or 'не указан'}\n"
            f"Дата регистрации: `{user[2]}`\n\n"
            f"💰 Баланс рублей: *{fmt_rub(user[3] or 0)}*\n"
            f"⭐ Баланс Stars: *{user[4] or 0} ★*"
        )
        await query.edit_message_text(text, reply_markup=back_menu())
        return
    
    # ===== ПОДДЕРЖКА =====
    if data == "support":
        await query.edit_message_text(
            f"*📞 Поддержка*\n\n"
            f"По всем вопросам обращайтесь:\n"
            f"👤 @{SUPPORT_USERNAME}",
            reply_markup=back_menu()
        )
        return
    
    # ===== ИНФОРМАЦИЯ =====
    if data == "info":
        await query.edit_message_text(
            "*ℹ️ Информация*\n\n"
            "• Покупка/продажа Stars осуществляется вручную через администратора.\n"
            "• Premium выдаётся официальным методом Telegram.\n"
            "• Внутренний баланс можно пополнить через СБП.\n\n"
            f"📢 Канал: @{CHANNEL_USERNAME}",
            reply_markup=back_menu()
        )
        return
    
    # ===== КАЛЬКУЛЯТОР =====
    if data == "calculator":
        await query.edit_message_text(
            f"*📊 Калькулятор*\n\n"
            f"Цена: 1 ★ = {STAR_PRICE_PER_ONE} ₽\n\n"
            f"15 ★ = {15 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"50 ★ = {50 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"100 ★ = {100 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"250 ★ = {250 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"500 ★ = {500 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"1000 ★ = {1000 * STAR_PRICE_PER_ONE:.0f} ₽\n"
            f"5000 ★ = {5000 * STAR_PRICE_PER_ONE:.0f} ₽",
            reply_markup=back_menu()
        )
        return
    
    # ===== АДМИН-ПАНЕЛЬ =====
    if data.startswith("admin"):
        if not is_admin(user_id):
            await query.edit_message_text("❌ Доступ запрещён!", reply_markup=main_menu())
            return
        
        if data == "admin_orders":
            orders = get_pending_orders()
            if not orders:
                await query.edit_message_text("📭 Нет активных заказов на Stars.", reply_markup=admin_menu())
                return
            
            text = "📦 *Активные заказы Stars*\n\n"
            for o in orders[:10]:
                text += f"#{o[0]} | {o[2]} ★ | {fmt_rub(o[3])} | {o[4]}\n"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        if data == "admin_sell":
            sells = get_pending_sell_requests()
            if not sells:
                await query.edit_message_text("📭 Нет заявок на продажу.", reply_markup=admin_menu())
                return
            
            text = "📤 *Заявки на продажу Stars*\n\n"
            for s in sells[:10]:
                text += f"#{s[0]} | {s[2]} ★ | {s[3]} ₽ | {s[4]}\n"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        if data == "admin_deposits":
            deposits = get_pending_deposits()
            if not deposits:
                await query.edit_message_text("📭 Нет заявок на пополнение.", reply_markup=admin_menu())
                return
            
            text = "💰 *Заявки на пополнение*\n\n"
            for d in deposits[:10]:
                text += f"#{d[0]} | {fmt_rub(d[2])} | {d[3]}\n"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        if data == "admin_premium":
            premiums = get_pending_premium()
            if not premiums:
                await query.edit_message_text("📭 Нет заявок на Premium.", reply_markup=admin_menu())
                return
            
            text = "👑 *Заявки на Premium*\n\n"
            for p in premiums[:10]:
                text += f"#{p[0]} | {p[2]} мес. | {fmt_rub(p[3])} | {p[4]} ★\n"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        if data == "admin_withdrawals":
            withdrawals = get_pending_withdrawals()
            if not withdrawals:
                await query.edit_message_text("📭 Нет заявок на вывод.", reply_markup=admin_menu())
                return
            
            text = "💸 *Заявки на вывод*\n\n"
            for w in withdrawals[:10]:
                text += f"#{w[0]} | {fmt_rub(w[2])} | {w[3]}\n"
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        if data == "admin_stats":
            users, orders, completed, stars_sold, rub_earned = get_stats()
            text = (
                f"*📊 Статистика*\n\n"
                f"👥 Пользователей: {users}\n"
                f"📦 Заказов: {orders}\n"
                f"✅ Выполнено: {completed}\n"
                f"⭐ Продано Stars: {stars_sold}\n"
                f"💰 Заработано: {fmt_rub(rub_earned)}"
            )
            await query.edit_message_text(text, reply_markup=admin_menu())
            return
        
        # Решения админа
        if data.startswith("approve_") or data.startswith("reject_"):
            parts = data.split("_")
            action = parts[0]
            kind = parts[1]
            item_id = int(parts[2])
            
            if kind == "order":
                order = get_order(item_id)
                if not order:
                    await query.edit_message_text("Заказ не найден.", reply_markup=admin_menu())
                    return
                
                if action == "approve":
                    update_order_status(item_id, "completed")
                    update_balance(order[1], stars_amount=order[2])
                    await context.bot.send_message(
                        order[1],
                        f"✅ Заказ #{item_id} выполнен!\n"
                        f"⭐ {order[2]} ★ зачислены на баланс."
                    )
                    await query.edit_message_text(f"✅ Заказ #{item_id} подтверждён.", reply_markup=admin_menu())
                else:
                    update_order_status(item_id, "rejected")
                    await context.bot.send_message(
                        order[1],
                        f"❌ Заказ #{item_id} отклонён."
                    )
                    await query.edit_message_text(f"❌ Заказ #{item_id} отклонён.", reply_markup=admin_menu())
                return
            
            if kind == "sell":
                sell = get_sell_request(item_id)
                if not sell:
                    await query.edit_message_text("Заявка не найдена.", reply_markup=admin_menu())
                    return
                
                if action == "approve":
                    update_sell_request_status(item_id, "approved")
                    await context.bot.send_message(
                        sell[1],
                        f"✅ Заявка на продажу #{item_id} одобрена!\n"
                        f"Администратор свяжется с вами для завершения сделки."
                    )
                    await query.edit_message_text(f"✅ Заявка #{item_id} одобрена.", reply_markup=admin_menu())
                else:
                    update_sell_request_status(item_id, "rejected")
                    await context.bot.send_message(
                        sell[1],
                        f"❌ Заявка на продажу #{item_id} отклонена."
                    )
                    await query.edit_message_text(f"❌ Заявка #{item_id} отклонена.", reply_markup=admin_menu())
                return
            
            if kind == "deposit":
                dep = get_deposit(item_id)
                if not dep:
                    await query.edit_message_text("Заявка не найдена.", reply_markup=admin_menu())
                    return
                
                if action == "approve":
                    update_deposit_status(item_id, "completed")
                    update_balance(dep[1], rub_amount=dep[2])
                    await context.bot.send_message(
                        dep[1],
                        f"✅ Пополнение #{item_id} подтверждено!\n"
                        f"💰 {fmt_rub(dep[2])} зачислены на баланс."
                    )
                    await query.edit_message_text(f"✅ Пополнение #{item_id} подтверждено.", reply_markup=admin_menu())
                else:
                    update_deposit_status(item_id, "rejected")
                    await context.bot.send_message(
                        dep[1],
                        f"❌ Пополнение #{item_id} отклонено."
                    )
                    await query.edit_message_text(f"❌ Пополнение #{item_id} отклонено.", reply_markup=admin_menu())
                return
            
            if kind == "withdraw":
                w = get_withdrawal(item_id)
                if not w:
                    await query.edit_message_text("Заявка не найдена.", reply_markup=admin_menu())
                    return
                
                if action == "approve":
                    update_withdrawal_status(item_id, "completed")
                    await context.bot.send_message(
                        w[1],
                        f"✅ Заявка на вывод #{item_id} подтверждена!\n"
                        f"Администратор переведёт {fmt_rub(w[2])}."
                    )
                    await query.edit_message_text(f"✅ Вывод #{item_id} подтверждён.", reply_markup=admin_menu())
                else:
                    update_withdrawal_status(item_id, "rejected")
                    update_balance(w[1], rub_amount=w[2])
                    await context.bot.send_message(
                        w[1],
                        f"❌ Заявка на вывод #{item_id} отклонена.\n"
                        f"Средства возвращены на баланс."
                    )
                    await query.edit_message_text(f"❌ Вывод #{item_id} отклонён.", reply_markup=admin_menu())
                return
            
            if kind == "premium":
                p = get_premium_order(item_id)
                if not p:
                    await query.edit_message_text("Заявка не найдена.", reply_markup=admin_menu())
                    return
                
                if action == "approve":
                    update_premium_status(item_id, "completed")
                    await context.bot.send_message(
                        p[1],
                        f"✅ Premium #{item_id} подтверждён!\n"
                        f"Подписка на {p[2]} мес. активирована."
                    )
                    await query.edit_message_text(f"✅ Premium #{item_id} подтверждён.", reply_markup=admin_menu())
                else:
                    update_premium_status(item_id, "rejected")
                    await context.bot.send_message(
                        p[1],
                        f"❌ Заявка на Premium #{item_id} отклонена."
                    )
                    await query.edit_message_text(f"❌ Premium #{item_id} отклонён.", reply_markup=admin_menu())
                return

# ========== ОБРАБОТЧИК ФАЙЛОВ ==========
async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    flow = context.user_data.get('flow', '')
    
    if not flow.startswith("order_receipt_") and flow != "deposit_receipt" and not flow.startswith("premium_receipt_"):
        await update.message.reply_text(
            "Сначала оформите заявку через меню.",
            reply_markup=main_menu()
        )
        return
    
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Отправьте фото или документ с чеком.")
        return
    
    if flow.startswith("order_receipt_"):
        order_id = int(flow.split("_")[2])
        update_order_status(order_id, "receipt_sent")
        context.user_data['flow'] = ''
        await update.message.reply_text(
            f"✅ Чек по заказу #{order_id} получен!\n"
            "Администратор проверит оплату.",
            reply_markup=main_menu()
        )
        await notify_admin(f"📦 Чек по заказу #{order_id}\nПользователь: @{update.effective_user.username or user_id}")
    
    elif flow == "deposit_receipt":
        dep_id = create_deposit(user_id, 0, file_id)
        update_deposit_status(dep_id, "receipt_sent")
        context.user_data['flow'] = ''
        await update.message.reply_text(
            f"✅ Чек по пополнению получен!",
            reply_markup=main_menu()
        )
        await notify_admin(f"💰 Чек по пополнению #{dep_id}\nПользователь: @{update.effective_user.username or user_id}")
    
    elif flow.startswith("premium_receipt_"):
        p_id = int(flow.split("_")[2])
        update_premium_status(p_id, "receipt_sent")
        context.user_data['flow'] = ''
        await update.message.reply_text(
            f"✅ Чек по Premium #{p_id} получен!",
            reply_markup=main_menu()
        )
        await notify_admin(f"👑 Чек по Premium #{p_id}\nПользователь: @{update.effective_user.username or user_id}")

# ========== ТЕКСТОВЫЙ ВВОД ==========
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    flow = context.user_data.get('flow', '')
    
    if flow == "sell_custom":
        try:
            stars = int(text)
            if stars < 15:
                await update.message.reply_text("Минимальное количество — 15 ★.")
                return
            req_id = create_sell_request(user_id, stars, 0)
            await notify_admin(f"📤 Заявка на продажу #{req_id}\nПользователь: @{update.effective_user.username or user_id}\nStars: {stars} ★")
            context.user_data['flow'] = ''
            await update.message.reply_text(
                f"✅ Заявка #{req_id} создана.\nStars: {stars} ★",
                reply_markup=main_menu()
            )
        except ValueError:
            await update.message.reply_text("Введите число.")
        return
    
    if flow == "withdraw_custom":
        try:
            amount = float(text)
            if amount < 100:
                await update.message.reply_text("Минимальная сумма вывода — 100 ₽.")
                return
            user = get_user(user_id)
            if user[3] < amount:
                await update.message.reply_text(f"Недостаточно средств. Доступно: {fmt_rub(user[3])}")
                return
            w_id = create_withdrawal(user_id, amount)
            update_balance(user_id, rub_amount=-amount)
            await notify_admin(f"💸 Заявка на вывод #{w_id}\nПользователь: @{update.effective_user.username or user_id}\nСумма: {fmt_rub(amount)}")
            context.user_data['flow'] = ''
            await update.message.reply_text(
                f"✅ Заявка на вывод #{w_id} создана.",
                reply_markup=main_menu()
            )
        except ValueError:
            await update.message.reply_text("Введите число.")
        return

# ========== УВЕДОМЛЕНИЯ ==========
async def notify_admin(text):
    try:
        await Application.builder().token(BOT_TOKEN).build().bot.send_message(ADMIN_ID, text, parse_mode=ParseMode.MARKDOWN)
    except:
        pass

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receipt_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("🚀 Starsov Bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()