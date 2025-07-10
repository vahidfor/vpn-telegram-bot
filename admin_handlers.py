from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import sqlite3

ADMIN_IDS = [113216719]  # آیدی عددی ادمین‌ها اینجا بذار

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ دسترسی ندارید.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 کاربران منتظر تأیید", callback_data="pending_users")],
        [InlineKeyboardButton("💳 مدیریت اعتبار", callback_data="manage_credit")],
        [InlineKeyboardButton("💰 تنظیم قیمت سرویس‌ها", callback_data="set_prices")],
    ]
    await update.message.reply_text("🛠 پنل مدیریت:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "pending_users":
        await show_pending_users(query, context)
    elif data == "manage_credit":
        await query.edit_message_text("برای مدیریت اعتبار کاربر، دستور زیر را بفرست:\n\n`/credit user_id مقدار`", parse_mode="HTML")
    elif data == "set_prices":
        await query.edit_message_text("برای تنظیم قیمت سرویس:\n\n`/setprice openvpn 150`")

async def show_pending_users(query, context):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT telegram_id, full_name, phone, os FROM users WHERE approved = 0")
    users = c.fetchall()
    conn.close()

    if not users:
        await query.edit_message_text("✅ کاربر منتظر تأیید وجود ندارد.")
        return

    for u in users:
        tid, name, phone, osys = u
        keyboard = [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{tid}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject_{tid}")
            ]
        ]
        text = f"👤 <b>{name or 'بدون نام'}</b>\n📱 {phone or 'نامشخص'}\n🖥 {osys or 'نامشخص'}\n🆔 {tid}"
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = int(update.callback_query.data.split("_")[1])
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE telegram_id = ?", (tid,))
    conn.commit()
    conn.close()

    await update.callback_query.answer("✅ تأیید شد")
    await update.callback_query.edit_message_text(f"✅ کاربر {tid} تأیید شد.")
    await context.bot.send_message(tid, "✅ حساب شما تأیید شد. اکنون می‌توانید سرویس درخواست کنید.")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = int(update.callback_query.data.split("_")[1])
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE telegram_id = ?", (tid,))
    conn.commit()
    conn.close()

    await update.callback_query.answer("❌ رد شد")
    await update.callback_query.edit_message_text(f"❌ کاربر {tid} رد شد.")
    await context.bot.send_message(tid, "❌ درخواست شما رد شد. لطفاً دوباره تلاش کنید.")

async def set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    try:
        _, service, price = update.message.text.split()
        price = int(price)
    except:
        await update.message.reply_text("فرمت اشتباه است. مثال:\n/setprice openvpn 150")
        return

    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE service_prices SET price=? WHERE service=?", (price, service.lower()))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ قیمت {service} تنظیم شد به {price} تومان")

async def set_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    try:
        _, uid, amount = update.message.text.split()
        uid = int(uid)
        amount = int(amount)
    except:
        await update.message.reply_text("فرمت اشتباه است. مثال:\n/credit 123456 20000")
        return

    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET credit = credit + ? WHERE telegram_id = ?", (amount, uid))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ اعتبار کاربر {uid} تنظیم شد ({'+' if amount>=0 else ''}{amount} تومان)")
    await context.bot.send_message(uid, f"💳 اعتبار شما توسط ادمین بروزرسانی شد: {amount:+,} تومان")

def setup_admin_handlers(app):
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^(pending_users|manage_credit|set_prices)$"))
    app.add_handler(CallbackQueryHandler(approve_user, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(reject_user, pattern="^reject_"))
    app.add_handler(CommandHandler("setprice", set_price))
    app.add_handler(CommandHandler("credit", set_credit))
