# -*- coding: utf-8 -*-
"""
Starsov Bot — покупка звёзд, Premium, Steam, партнёрская программа, игры
"""

import os
import sqlite3
import json
import random
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ========== КОНФИГУРАЦИЯ ==========
TOKEN = "8856609164:AAGJ_Hnsc5eWbNoCxrUQIEYkuIYTWTPwYzc"
ADMIN_ID = 5141751465  # твой Telegram ID

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
            total_earned REAL DEFAULT 0.0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount TEXT,
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
    conn.commit()
    conn.close()

# ========== РАБОТА С БАЗОЙ ==========
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def create_user(user_id, username, referrer_id=0):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    ref_code = f"r{user_id}"
    cur.execute('''
        INSERT OR IGNORE INTO users (user_id, username, ref_code, referrer_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, ref_code, referrer_id))
    if referrer_id:
        # Начисляем 10% рефереру (как в боте)
        cur.execute('UPDATE users SET ref_balance = ref_balance + 0.1 WHERE user_id = ?', (referrer_id,))
        cur.execute('UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?', (referrer_id,))
    conn.commit()
    conn.close()

def update_ref_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('UPDATE users SET ref_balance = ref_balance + ?, total_earned = total_earned + ? WHERE user_id = ?', (amount, amount, user_id))
    conn.commit()
    conn.close()

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

def get_total_earned(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT total_earned FROM users WHERE user_id = ?', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0.0

def create_order(user_id, order_type, amount):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO orders (user_id, type, amount, date) VALUES (?, ?, ?, ?)',
                (user_id, order_type, amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def create_withdrawal(user_id, amount, wallet):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('INSERT INTO withdrawals (user_id, amount, wallet, date) VALUES (?, ?, ?, ?)',
                (user_id, amount, wallet, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_pending_withdrawals():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('SELECT id, user_id, amount, wallet, date FROM withdrawals WHERE status = "pending"')
    result = cur.fetchall()
    conn.close()
    return result

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

# ========== КНОПКИ ==========
def main_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Купить Звезды", callback_data="buy_stars")],
        [InlineKeyboardButton("👑 Телеграм Премиум", callback_data="buy_premium")],
        [InlineKeyboardButton("🎁 Пополнить Steam", callback_data="buy_steam")],
        [InlineKeyboardButton("👥 Партнерская Программа", callback_data="referral")],
    ])
    return markup

def payment_menu(order_type, amount, target_user=None):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 СБП (Рубли) #1", callback_data=f"pay_sbp1_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("💳 СБП (Рубли) #2", callback_data=f"pay_sbp2_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🪙 TON", callback_data=f"pay_ton_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("₿ Крипта / USDT", callback_data=f"pay_crypto_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🤖 CryptoBot", callback_data=f"pay_cryptobot_{order_type}_{amount}_{target_user or 'me'}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
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

def admin_menu():
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📤 Заявки на вывод", callback_data="admin_withdrawals")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
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
    
    await update.message.reply_text(
        "🌟 **Добро пожаловать!**\n\n"
        "Здесь можно приобрести Telegram звезды без верификации KYC и дешевле чем в приложении,\n"
        "а также пополнить Steam баланс.\n\n"
        "❗ Чтобы продолжить, просто выбери действие ниже:",
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
            "🌟 **Главное меню:**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПОКУПКА ЗВЁЗД =====
    if data == "buy_stars":
        await query.edit_message_text(
            "⭐ **Купить Звезды**\n\n"
            "Выберите количество звезд:",
            reply_markup=stars_amount_menu()
        )
        return
    
    if data == "buy_for_friend":
        await query.edit_message_text(
            "💬 **Покупка для друга**\n\n"
            "Введите @username друга или отправьте его ID.\n\n"
            "После ввода выберите количество звезд."
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
            f"⭐ **Покупка {amount} звезд**\n\n"
            f"Покупка для: @{query.from_user.username or 'вас'}\n\n"
            "Выберите способ оплаты:",
            reply_markup=payment_menu("stars", amount, target)
        )
        return
    
    # ===== ТЕЛЕГРАМ ПРЕМИУМ =====
    if data == "buy_premium":
        await query.edit_message_text(
            "👑 **Telegram Premium**\n\n"
            "Выберите срок подписки:",
            reply_markup=premium_menu()
        )
        return
    
    if data.startswith("premium_"):
        months = data.split("_")[1]
        price = {"3": 3, "6": 5.5, "12": 10}.get(months, 3)
        await query.edit_message_text(
            f"👑 **Telegram Premium - {months} мес.**\n\n"
            f"Цена: {price} TON\n\n"
            "Выберите способ оплаты:",
            reply_markup=payment_menu("premium", months)
        )
        return
    
    # ===== STEAM =====
    if data == "buy_steam":
        await query.edit_message_text(
            "🎁 **Пополнить Steam**\n\n"
            "Выберите сумму:",
            reply_markup=steam_menu()
        )
        return
    
    if data.startswith("steam_"):
        amount = data.split("_")[1]
        await query.edit_message_text(
            f"🎁 **Steam пополнение на {amount}$**\n\n"
            "Выберите способ оплаты:",
            reply_markup=payment_menu("steam", amount)
        )
        return
    
    # ===== ОПЛАТА =====
    if data.startswith("pay_"):
        parts = data.split("_")
        method = parts[1]
        order_type = parts[2]
        amount = parts[3]
        target = parts[4] if len(parts) > 4 else "me"
        
        # Создаём заказ
        create_order(user_id, f"{order_type}_{amount}", amount)
        
        # Отправляем реквизиты
        if method == "sbp1":
            text = f"💳 **Оплата по СБП #1**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount*0.5} ₽\n\n"
            text += "📱 **Номер карты:** 2200 1234 5678 9012\n"
            text += "🏦 **Банк:** Т-Банк\n"
            text += "👤 **Получатель:** Иванов И.И.\n\n"
            text += "❗ Счет действителен 30 минут.\n"
            text += "После оплаты пришлите чек в этот чат."
        elif method == "sbp2":
            text = f"💳 **Оплата по СБП #2**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount*0.45} ₽\n\n"
            text += "📱 **Номер карты:** 2200 9876 5432 1098\n"
            text += "🏦 **Банк:** Сбербанк\n"
            text += "👤 **Получатель:** Петров П.П.\n\n"
            text += "❗ Счет действителен 30 минут.\n"
            text += "После оплаты пришлите чек в этот чат."
        elif method == "ton":
            text = f"🪙 **Оплата TON**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount*0.02} TON\n\n"
            text += "📍 **Адрес для перевода:**\n"
            text += "UQB... (ваш TON-адрес)\n\n"
            text += "❗ Счет действителен 30 минут."
        elif method == "crypto":
            text = f"₿ **Оплата криптовалютой**\n\n"
            text += f"Заказ: {order_type} на {amount}\n"
            text += f"Сумма: {amount*0.015} USDT\n\n"
            text += "📍 **Адрес USDT (TRC20):**\n"
            text += "T... (ваш USDT-адрес)\n\n"
            text += "❗ Счет действителен 30 минут."
        else:  # cryptobot
            text = f"🤖 **Оплата через CryptoBot**\n\n"
            text += f"Заказ: {order_type} на {amount}\n\n"
            text += "Перейдите в @CryptoBot и оплатите счёт."
        
        text += "\n\nПосле оплаты отправьте скриншот чека."
        
        await query.edit_message_text(
            text,
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return
    
    # ===== ПАРТНЁРСКАЯ ПРОГРАММА =====
    if data == "referral":
        ref_count = get_ref_count(user_id)
        ref_balance = get_ref_balance(user_id)
        total_earned = get_total_earned(user_id)
        ref_link = f"https://t.me/{context.bot.username}?start=r{user_id}"
        
        text = "👥 **Партнерская программа**\n\n"
        text += "Приглашайте людей и получайте 10% от нашего дохода НАВСЕГДА!\n\n"
        text += f"**Ваша партнерская ссылка:**\n"
        text += f"`{ref_link}`\n\n"
        text += f"**Статистика вашей ссылки:**\n"
        text += f"Рефералов: {ref_count}\n"
        text += f"Баланс: {ref_balance} TON\n"
        text += f"Всего заработано: {total_earned} TON\n\n"
        text += "Минимальная сумма выплаты - 0.5 TON"
        
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Вывести", callback_data="withdraw_ref")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return
    
    if data == "withdraw_ref":
        await query.edit_message_text(
            "💳 **Вывод средств**\n\n"
            "Введите сумму для вывода (минимум 0.5 TON)\n"
            "и ваш кошелёк TON.\n\n"
            "Формат: `0.5 UQB...`"
        )
        context.user_data['withdraw'] = True
        return
    
    # ===== ИГРЫ =====
    if data == "games":
        await query.edit_message_text(
            "🎮 **Выбери игру**",
            reply_markup=games_menu()
        )
        return
    
    if data.startswith("game_"):
        game = data.split("_")[1]
        await query.edit_message_text(
            f"🎯 **Игра: {game.capitalize()}**\n\n"
            f"Попади в цель - забери подарок!\n"
            f"Шанс успеха: 40%\n\n"
            "Выбери цену приза:",
            reply_markup=game_prize_menu(game)
        )
        return
    
    if data.startswith("prize_"):
        parts = data.split("_")
        game = parts[1]
        prize = parts[2]
        
        success = random.random() < 0.4
        if success:
            # 10% от приза идёт рефереру
            ref_id = get_referrer_id(user_id)
            if ref_id:
                update_ref_balance(ref_id, int(prize) * 0.01)
            
            await query.edit_message_text(
                f"🎉 **Поздравляем!**\n\n"
                f"Ты выиграл {prize} ★ в игре {game.capitalize()}!\n\n"
                f"Награда зачислена на баланс.",
                reply_markup=games_menu()
            )
        else:
            await query.edit_message_text(
                f"😢 **Не повезло!**\n\n"
                f"Попробуй ещё раз!",
                reply_markup=games_menu()
            )
        return
    
    # ===== АДМИН =====
    if data == "admin_stats" and user_id == ADMIN_ID:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM users')
        users_count = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM orders')
        orders_count = cur.fetchone()[0]
        conn.close()
        await query.edit_message_text(
            f"📊 **Статистика**\n\n"
            f"👥 Пользователей: {users_count}\n"
            f"📦 Заказов: {orders_count}",
            reply_markup=admin_menu(),
            parse_mode="Markdown"
        )
        return

# ========== ОБРАБОТЧИК ЧЕКОВ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Обработка вывода
    if context.user_data.get('withdraw'):
        try:
            parts = text.split()
            amount = float(parts[0])
            wallet = parts[1] if len(parts) > 1 else ""
            if amount >= 0.5:
                create_withdrawal(user_id, amount, wallet)
                await update.message.reply_text(
                    "✅ Заявка на вывод создана!\n"
                    "Ожидайте обработки администратором."
                )
            else:
                await update.message.reply_text("❌ Минимальная сумма вывода 0.5 TON")
        except:
            await update.message.reply_text("❌ Неверный формат! Используйте: `0.5 UQB...`")
        context.user_data['withdraw'] = False
        return
    
    # Обработка покупки для друга
    if context.user_data.get('buy_for_friend'):
        # Пытаемся найти пользователя по username или ID
        target = text.strip()
        context.user_data['buy_for_friend'] = False
        await update.message.reply_text(
            "Выберите количество звезд для друга:",
            reply_markup=stars_amount_menu()
        )
        return
    
    # Проверка на чек (скриншот)
    if update.message.photo:
        await update.message.reply_text(
            "✅ Чек получен!\n"
            "Администратор проверит оплату и выполнит заказ в ближайшее время."
        )
        # Уведомление админу
        await context.bot.send_message(
            ADMIN_ID,
            f"📤 Новый чек от @{update.effective_user.username or 'пользователя'}!\n"
            f"🆔 ID: {user_id}"
        )
        return

# ========== АДМИН-КОМАНДЫ ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён!")
        return
    await update.message.reply_text("🔧 **Админ-панель**", reply_markup=admin_menu(), parse_mode="Markdown")

# ========== ЗАПУСК ==========
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, handle_message))
    
    print("🚀 Starsov Bot запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()