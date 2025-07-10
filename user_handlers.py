from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CommandHandler, filters
)
from config import REQUEST_INFO
import sqlite3

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT approved FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()

    if user:
        if user[0] == 1:
            await update.message.reply_text("✅ شما قبلاً تأیید شده‌اید.")
        else:
            await update.message.reply_text("⏳ شما هنوز تأیید نشده‌اید. لطفاً برای دریافت سرویس، ابتدا درخواست ارسال کنید.")
    else:
        c.execute("INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("👋 خوش آمدید! لطفاً برای دریافت سرویس ابتدا درخواست خود را از منو ارسال کنید.")
    conn.close()

async def request_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT approved FROM users WHERE telegram_id=?", (user_id,))
    user = c.fetchone()

    if not user or user[0] != 1:
        await update.message.reply_text(
            "لطفاً شماره موبایل خود را ارسال کنید:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("ارسال شماره من ☎️", request_contact=True)]],
                resize_keyboard=True
            )
        )
        return REQUEST_INFO
    else:
        await update.message.reply_text("✅ شما قبلاً تأیید شده‌اید و می‌توانید سرویس دریافت کنید.")
    conn.close()
    return ConversationHandler.END

async def save_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number
    user_id = update.effective_user.id

    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET phone=? WHERE telegram_id=?", (phone, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "سیستم عامل خود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["اندروید", "iOS"], ["ویندوز"]],
            resize_keyboard=True
        )
    )
    return REQUEST_INFO

async def save_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os_name = update.message.text
    user_id = update.effective_user.id

    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET os=? WHERE telegram_id=?", (os_name, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "لطفاً نام کامل خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return REQUEST_INFO

async def save_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text
    user_id = update.effective_user.id

    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET full_name=? WHERE telegram_id=?", (full_name, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ اطلاعات شما ذخیره شد. لطفاً منتظر تأیید توسط ادمین باشید.")
    return ConversationHandler.END

async def my_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT credit FROM users WHERE telegram_id=?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        await update.message.reply_text(f"💰 اعتبار شما: {result[0]:,} تومان")
    else:
        await update.message.reply_text("❗ شما هنوز ثبت‌نام نکرده‌اید.")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT approved FROM users WHERE telegram_id=?", (user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        status = "✅ تأیید شده" if result[0] == 1 else "⏳ در انتظار تأیید"
        await update.message.reply_text(f"📋 وضعیت حساب شما: {status}")
    else:
        await update.message.reply_text("❗ حساب شما یافت نشد.")

async def get_app_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📱 لطفاً نوع دستگاه خود را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(
            [["اندروید", "iOS"], ["ویندوز"]],
            resize_keyboard=True
        )
    )
    return 777

async def send_app_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    device = update.message.text.lower()
    text = ""

    if "اندروید" in device:
        text = (
            "📥 دانلود OpenVPN:\n"
            "https://play.google.com/store/apps/details?id=net.openvpn.openvpn\n\n"
            "📥 دانلود V2Ray:\n"
            "https://play.google.com/store/apps/details?id=com.v2ray.ang"
        )
    elif "ios" in device or "آیفون" in device:
        text = (
            "📥 OpenVPN:\n"
            "https://apps.apple.com/us/app/openvpn-connect/id590379981\n\n"
            "📥 V2Ray:\n"
            "https://apps.apple.com/app/id6448898396"
        )
    elif "ویندوز" in device:
        text = (
            "📥 OpenVPN:\n"
            "https://openvpn.net/client-connect-vpn-for-windows/\n\n"
            "📥 V2RayN:\n"
            "https://github.com/2dust/v2rayN/releases"
        )
    else:
        text = "❗ نوع دستگاه ناشناخته است. لطفاً دوباره انتخاب کنید."

    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def setup_user_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myinfo", my_status))
    app.add_handler(CommandHandler("score", my_credit))

    app.add_handler(MessageHandler(filters.Regex("^📃 دریافت برنامه$"), get_app_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_app_link))

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🌐 دریافت سرویس‌ها$"), request_service)],
        states={
            REQUEST_INFO: [
                MessageHandler(filters.CONTACT, save_contact),
                MessageHandler(filters.Regex("^(اندروید|iOS|ویندوز)$"), save_os),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_full_name),
            ],
            777: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_app_link)]
        },
        fallbacks=[],
    )
    app.add_handler(conv)
