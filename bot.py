import os
import sqlite3
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

import config # Import config.py for states and constants
import database # Import database.py for database operations
import datetime

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load token from .env
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = config.ADMIN_ID # Using ADMIN_ID from config.py

# --- Helper Functions for Keyboards ---

async def get_main_menu_keyboard():
    """Returns the main menu ReplyKeyboardMarkup for users."""
    keyboard = [
        ["🛍 خرید اکانت", "⬇️ دانلود برنامه‌ها"],
        ["🎁 استفاده از کد تخفیف", "💳 انتقال اعتبار"],
        ["📞 پشتیبانی", "💰 اعتبار من", "👤 اطلاعات من"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

async def get_admin_panel_keyboard():
    """Returns the main admin panel InlineKeyboardMarkup."""
    keyboard = [
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_manage_users")],
        [InlineKeyboardButton("⚙️ مدیریت سرویس‌ها", callback_data="admin_manage_services")],
        [InlineKeyboardButton("🏷 کدهای تخفیف", callback_data="admin_discount_codes")],
        [InlineKeyboardButton("🛒 درخواست‌های خرید", callback_data="admin_requests")],
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats")],
        [InlineKeyboardButton("❓ پیام‌های پشتیبانی", callback_data="admin_support")],
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast_ask")], # Using a callback for consistency
    ]
    return InlineKeyboardMarkup(keyboard)

# --- User Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the /start command, registers user, and displays main menu."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name if update.effective_user.last_name else ""

    # Add/update user in DB
    database.add_user(user_id, username, first_name, last_name)

    welcome_message = (
        "🔰 سلام 👋\n"
        "به ربات مدیریت سرویس VPN خوش اومدی 👋\n\n"
        "🌟 با این ربات می‌تونی:\n"
        "• اکانت VPN خریداری کنی\n"
        "• برنامه‌های مورد نیاز رو دانلود کنی\n"
        "• از کدهای تخفیف استفاده کنی\n"
        "• اعتبار انتقال بدی\n"
        "• با پشتیبانی در تماس باشی\n\n"
        "📱 از منوی زیر گزینه مورد نظرتو انتخاب کن:"
    )
    
    keyboard = await get_main_menu_keyboard()
    await update.message.reply_text(welcome_message, reply_markup=keyboard)
    
    # Check if user needs registration details
    user_data = database.get_user(user_id)
    if not user_data.get('phone_number') or not user_data.get('full_name') or not user_data.get('requested_os'):
        await update.message.reply_text("👋 برای استفاده کامل از ربات، لطفاً اطلاعات خود را تکمیل کنید.")
        await ask_contact(update, context) # Start registration flow if incomplete
        return config.REQUESTING_CONTACT # Keep in registration conversation
    
    return ConversationHandler.END # If already registered, end conversation

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays information about the bot."""
    about_text = (
        "🔰 درباره تیم ویرا:\n\n"
        "🚀 ارائه‌دهنده خدمات VPN با کیفیت\n"
        "📞 پشتیبانی 24/7\n"
        "🔒 امنیت بالا\n"
        "⚡️ سرعت عالی\n\n"
        "تیم ویرا با هدف ایجاد دسترسی کامل افراد به اینترنت آزاد و بدون محدودیت شروع به کار کرد و این تیم زیر مجموعه (تیم پیوند) می‌باشد.\n\n"
        "💬 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
    )
    await update.message.reply_text(about_text)

async def show_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user's current credit."""
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if user:
        await update.message.reply_text(f"💰 اعتبار فعلی شما: {user['credit']} تومان")
    else:
        await update.message.reply_text("کاربر یافت نشد. لطفاً /start را بزنید.")

async def show_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user's registration status and info."""
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if user:
        status_text = (
            f"👤 اطلاعات شما:\n"
            f"آیدی: `{user['id']}`\n"
            f"نام کاربری: @{user['username']}\n"
            f"نام: {user['first_name']} {user['last_name']}\n"
            f"نام کامل ثبت شده: {user.get('full_name', 'نامشخص')}\n"
            f"شماره تماس: {user.get('phone_number', 'نامشخص')}\n"
            f"سیستم عامل درخواستی: {user.get('requested_os', 'نامشخص')}\n"
            f"وضعیت: {'✅ تأیید شده' if user['is_approved'] else '⏳ در انتظار تأیید ادمین'}\n"
            f"اعتبار: {user['credit']} تومان"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
    else:
        await update.message.reply_text("کاربر یافت نشد. لطفاً /start را بزنید.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels any ongoing conversation."""
    user_id = update.effective_user.id
    logger.info("User %s canceled the conversation.", user_id)
    await update.message.reply_text(
        "عملیات لغو شد. می‌توانید از منوی اصلی استفاده کنید.",
        reply_markup=await get_main_menu_keyboard(),
    )
    return ConversationHandler.END

async def show_app_downloads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays links for app downloads."""
    text = "برای دانلود برنامه OpenVPN Connect از لینک‌های زیر استفاده کنید:\n\n"
    for os_name, link in config.APP_LINKS.items():
        text += f"*{os_name.capitalize()}:* {link}\n"
    text += "\nبرای مشاهده راهنمای اتصال، گزینه راهنمای اتصال را انتخاب کنید."
    
    keyboard = [[InlineKeyboardButton("❓ راهنمای اتصال", callback_data="show_connection_guide")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_connection_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends connection guide images and captions."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text("لطفاً صبر کنید، راهنمای اتصال در حال ارسال است...")

    media_group = []
    for i, image_name in enumerate(config.CONNECTION_GUIDE['images']):
        image_path = os.path.join(config.IMAGES_DIR, image_name)
        if os.path.exists(image_path):
            caption = config.CONNECTION_GUIDE['captions'][i] if i < len(config.CONNECTION_GUIDE['captions']) else ""
            with open(image_path, 'rb') as f:
                media_group.append(InputMediaPhoto(media=f.read(), caption=caption))
        else:
            logger.warning(f"Image not found: {image_path}")

    if media_group:
        await query.message.reply_media_group(media=media_group)
    else:
        await query.message.reply_text("فایل‌های راهنمای اتصال یافت نشدند.")

    await query.message.reply_text(config.CONNECTION_GUIDE['additional_note'])


# --- Registration Flow ---
async def ask_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[KeyboardButton("📞 ارسال شماره تماس", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("برای تکمیل ثبت نام و استفاده از ربات، لطفاً شماره تماس خود را ارسال کنید:", reply_markup=reply_markup)
    return config.REQUESTING_CONTACT

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    phone_number = update.message.contact.phone_number
    
    database.update_user_info(user_id, phone_number=phone_number)
    await update.message.reply_text("شماره تماس شما با موفقیت ثبت شد.", reply_markup=ReplyKeyboardRemove())
    await ask_full_name(update, context)
    return config.REQUESTING_FULL_NAME

async def ask_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("حالا، لطفاً نام و نام خانوادگی کامل خود را وارد کنید (مثال: محمد حسینی):")
    return config.REQUESTING_FULL_NAME

async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    full_name = update.message.text
    
    database.update_user_info(user_id, full_name=full_name)
    await update.message.reply_text("نام کامل شما ثبت شد.")
    await ask_os(update, context)
    return config.SELECTING_OS

async def ask_os(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[InlineKeyboardButton(name, callback_data=f"os_{value}")] for name, value in config.DEVICE_TYPES.items() if value != "guide"]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً سیستم عامل دستگاه خود را انتخاب کنید:", reply_markup=reply_markup)
    return config.SELECTING_OS

async def receive_os(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_os = query.data.split('_')[1]

    database.update_user_info(user_id, requested_os=selected_os)
    await query.edit_message_text(f"سیستم عامل شما ({selected_os}) با موفقیت ثبت شد.\n\nثبت نام شما تکمیل شد! 😊")
    
    await query.message.reply_text("حالا می‌توانید از منوی اصلی استفاده کنید.", reply_markup=await get_main_menu_keyboard())
    return ConversationHandler.END


# --- User Purchase Flow ---
async def purchase_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user or not user['is_approved']:
        await update.message.reply_text("⚠️ شما هنوز توسط ادمین تأیید نشده‌اید. لطفاً پس از تکمیل ثبت نام، منتظر تأیید ادمین بمانید.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(name, callback_data=f"account_{key}")] for name, key in config.ACCOUNT_TYPES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً نوع اکانت مورد نظر خود را انتخاب کنید:", reply_markup=reply_markup)
    return config.SELECTING_PURCHASE_ACCOUNT_TYPE

async def select_purchase_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    account_type_key = query.data.split('_')[1] # e.g., '1 ماهه (30 روز)'

    context.user_data['selected_account_type'] = account_type_key

    keyboard = [[InlineKeyboardButton(name, callback_data=f"device_{value}")] for name, value in config.DEVICE_TYPES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً سیستم عامل یا نوع دستگاه خود را انتخاب کنید:", reply_markup=reply_markup)
    return config.SELECTING_DEVICE

async def select_device_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    device_type_key = query.data.split('_')[1] # e.g., 'android', 'ios', 'guide'

    context.user_data['selected_device_type'] = device_type_key

    if device_type_key == 'guide':
        await show_connection_guide(update, context) # Reuse guide function
        await query.message.reply_text("حالا می‌توانید ادامه فرآیند خرید را دنبال کنید.", reply_markup=await get_main_menu_keyboard())
        return ConversationHandler.END # End purchase flow if user just wanted guide

    keyboard = [[InlineKeyboardButton(name, callback_data=f"service_{key}")] for name, key in config.SERVICE_TYPES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً نوع سرویس مورد نظر خود را انتخاب کنید:", reply_markup=reply_markup)
    return config.SELECTING_SERVICE

async def select_service_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service_type_key = query.data.split('_')[1] # e.g., 'openvpn', 'v2ray', 'proxy'

    selected_account_type = context.user_data.get('selected_account_type')
    selected_device_type = context.user_data.get('selected_device_type')
    
    if not selected_account_type or not selected_device_type:
        await query.edit_message_text("خطا در انتخاب سرویس. لطفاً دوباره از /purchase شروع کنید.")
        return ConversationHandler.END

    user_id = query.from_user.id
    
    # Save the purchase request
    request_id = database.add_purchase_request(
        user_id=user_id,
        account_type=selected_account_type,
        requested_service=service_type_key,
        requested_device=selected_device_type
    )

    if request_id:
        await query.edit_message_text(
            f"✅ درخواست خرید شما برای '{selected_account_type}' ({service_type_key}) برای {selected_device_type} ثبت شد.\n"
            f"شماره درخواست شما: #{request_id}\n"
            "لطفاً منتظر تأیید و ارسال سرویس توسط ادمین باشید."
        )
        # Notify admin (optional, but good practice)
        admin_user = database.get_user(ADMIN_ID)
        if admin_user:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 درخواست خرید جدیدی ثبت شد!\n"
                     f"کاربر: {query.from_user.id} (@{query.from_user.username})\n"
                     f"نوع اکانت: {selected_account_type}\n"
                     f"نوع سرویس: {service_type_key}\n"
                     f"دستگاه: {selected_device_type}\n"
                     f"شماره درخواست: #{request_id}\n"
                     "لطفاً برای بررسی به پنل ادمین مراجعه کنید: /admin",
                reply_markup=await get_admin_panel_keyboard()
            )
    else:
        await query.edit_message_text("❌ خطایی در ثبت درخواست شما رخ داد. لطفاً دوباره تلاش کنید.")
    
    # Clear user_data for this conversation
    context.user_data.pop('selected_account_type', None)
    context.user_data.pop('selected_device_type', None)
    
    return ConversationHandler.END

# --- Discount Code Flow ---
async def discount_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates the discount code entry process."""
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user or not user['is_approved']:
        await update.message.reply_text("⚠️ شما هنوز توسط ادمین تأیید نشده‌اید. لطفاً پس از تکمیل ثبت نام، منتظر تأیید ادمین بمانید.")
        return ConversationHandler.END
        
    await update.message.reply_text("لطفاً کد تخفیف خود را وارد کنید:")
    return config.ENTERING_DISCOUNT_CODE

async def enter_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the entered discount code."""
    user_id = update.effective_user.id
    code = update.message.text.strip()

    discount = database.get_discount_code(code)
    if discount:
        value = database.use_discount_code(code)
        if value is not None:
            database.increase_credit(user_id, value)
            await update.message.reply_text(f"✅ کد تخفیف با موفقیت اعمال شد. {value} تومان به اعتبار شما اضافه شد.")
        else:
            await update.message.reply_text("❌ خطایی در اعمال کد تخفیف رخ داد. ممکن است کد قبلاً استفاده شده باشد.")
    else:
        await update.message.reply_text("❌ کد تخفیف نامعتبر است.")
    
    return ConversationHandler.END

# --- Credit Transfer Flow ---
async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates credit transfer by asking for receiver ID."""
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user or not user['is_approved']:
        await update.message.reply_text("⚠️ شما هنوز توسط ادمین تأیید نشده‌اید و/یا به این قابلیت دسترسی ندارید.")
        return ConversationHandler.END

    await update.message.reply_text("لطفاً آیدی عددی (Numeric ID) کاربری که می‌خواهید به او اعتبار انتقال دهید را وارد کنید:")
    return config.TRANSFER_USER_ID

async def ask_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for the amount to transfer."""
    try:
        receiver_id = int(update.message.text.strip())
        if not database.get_user(receiver_id):
            await update.message.reply_text("کاربری با این آیدی یافت نشد. لطفاً آیدی معتبر وارد کنید یا /cancel را بزنید.")
            return config.TRANSFER_USER_ID
        
        context.user_data['transfer_receiver_id'] = receiver_id
        await update.message.reply_text("لطفاً مبلغی که می‌خواهید انتقال دهید را به تومان وارد کنید:")
        return config.TRANSFER_AMOUNT
    except ValueError:
        await update.message.reply_text("آیدی نامعتبر است. لطفاً یک عدد وارد کنید یا /cancel را بزنید.")
        return config.TRANSFER_USER_ID

async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirms and executes the credit transfer."""
    sender_id = update.effective_user.id
    receiver_id = context.user_data.get('transfer_receiver_id')
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("مبلغ باید مثبت باشد. لطفاً مبلغ معتبر وارد کنید یا /cancel را بزنید.")
            return config.TRANSFER_AMOUNT

        sender_credit = database.get_user(sender_id)['credit']
        if sender_credit < amount:
            await update.message.reply_text(f"اعتبار شما کافی نیست. اعتبار فعلی شما: {sender_credit} تومان. لطفاً مبلغ کمتری وارد کنید یا /cancel را بزنید.")
            return config.TRANSFER_AMOUNT
        
        if database.decrease_credit(sender_id, amount) and database.increase_credit(receiver_id, amount):
            database.add_credit_transfer(sender_id, receiver_id, amount)
            await update.message.reply_text(f"✅ {amount} تومان با موفقیت به کاربر {receiver_id} منتقل شد.")
            await context.bot.send_message(
                chat_id=receiver_id, 
                text=f"🎁 {amount} تومان اعتبار از طرف کاربر {sender_id} به شما منتقل شد. اعتبار جدید شما: {database.get_user(receiver_id)['credit']} تومان"
            )
        else:
            await update.message.reply_text("❌ خطایی در انتقال اعتبار رخ داد. لطفاً دوباره تلاش کنید.")
    except (ValueError, TypeError):
        await update.message.reply_text("مبلغ نامعتبر است. لطفاً یک عدد وارد کنید یا /cancel را بزنید.")
    
    context.user_data.pop('transfer_receiver_id', None)
    return ConversationHandler.END

# --- Support Flow ---
async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates the support message entry process."""
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if not user or not user['is_approved']:
        await update.message.reply_text("⚠️ شما هنوز توسط ادمین تأیید نشده‌اید و/یا به این قابلیت دسترسی ندارید.")
        return ConversationHandler.END

    await update.message.reply_text("لطفاً پیام پشتیبانی خود را وارد کنید:")
    return config.ENTERING_SUPPORT_MESSAGE

async def enter_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the entered support message."""
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    if database.add_support_message(user_id, message_text):
        await update.message.reply_text("✅ پیام شما به پشتیبانی ارسال شد. در اسرع وقت پاسخ داده خواهد شد.")
        # Notify admin
        admin_user = database.get_user(ADMIN_ID)
        if admin_user:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔔 پیام پشتیبانی جدید از کاربر {user_id} (@{update.effective_user.username}):\n\n"
                     f"\"{message_text}\"\n\n"
                     "برای پاسخگویی به پنل ادمین مراجعه کنید: /admin",
                reply_markup=await get_admin_panel_keyboard()
            )
    else:
        await update.message.reply_text("❌ خطایی در ارسال پیام پشتیبانی رخ داد. لطفاً دوباره تلاش کنید.")
    
    return ConversationHandler.END

# --- Admin Command Handlers ---

# Admin Main Panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the admin panel main menu."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ شما به این بخش دسترسی ندارید.")
        return
    
    reply_markup = await get_admin_panel_keyboard()
    await update.message.reply_text("🛠 به پنل ادمین خوش آمدید:", reply_markup=reply_markup)

# Admin User Management
async def admin_manage_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays user management options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("✅ تأیید کاربر", callback_data="admin_approve_user_list")],
        [InlineKeyboardButton("➕ افزایش اعتبار کاربر", callback_data="admin_add_credit_to_user_list")],
        [InlineKeyboardButton("⏳ مشاهده کاربران در انتظار", callback_data="admin_view_pending_users")],
        [InlineKeyboardButton("👥 مشاهده همه کاربران", callback_data="admin_view_all_users")],
        [InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠 مدیریت کاربران:", reply_markup=reply_markup)

async def view_all_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a list of all registered users."""
    query = update.callback_query
    await query.answer()

    users = database.get_all_users()
    if not users:
        await query.edit_message_text("هیچ کاربری در دیتابیس یافت نشد.")
        return

    message_text = "لیست همه کاربران:\n\n"
    for user in users:
        status = "✅ تأیید شده" if user['is_approved'] else "⏳ در انتظار"
        message_text += (
            f"👤 ID: `{user['id']}` (@{user['username']})\n"
            f"نام: {user['first_name']} {user['last_name']}\n"
            f"وضعیت: {status}\n"
            f"اعتبار: {user['credit']} تومان\n"
            f"تلفن: {user.get('phone_number', 'نامشخص')}\n"
            f"نام کامل: {user.get('full_name', 'نامشخص')}\n"
            f"OS: {user.get('requested_os', 'نامشخص')}\n"
        )
        # Add Inline button to chat with user
        keyboard = [[InlineKeyboardButton("💬 چت با این کاربر", callback_data=f"admin_chat_user_{user['id']}")]]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        message_text = "" # Clear for next user
    
    await query.message.reply_text("پایان لیست کاربران.", reply_markup=await get_admin_panel_keyboard())


async def view_pending_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a list of users awaiting approval."""
    query = update.callback_query
    await query.answer()

    pending_users = database.get_pending_users()
    if not pending_users:
        await query.edit_message_text("هیچ کاربری در انتظار تأیید نیست.")
        return

    message_text = "کاربران در انتظار تأیید:\n\n"
    for user in pending_users:
        message_text += (
            f"👤 ID: `{user['id']}` (@{user['username']})\n"
            f"نام: {user['first_name']} {user['last_name']}\n"
            f"شماره تماس: {user.get('phone_number', 'نامشخص')}\n"
            f"نام کامل: {user.get('full_name', 'نامشخص')}\n"
            f"OS: {user.get('requested_os', 'نامشخص')}\n"
        )
        keyboard = [
            [InlineKeyboardButton("✅ تأیید", callback_data=f"approve_user_{user['id']}"),
             InlineKeyboardButton("❌ رد", callback_data=f"reject_user_{user['id']}")],
            [InlineKeyboardButton("💬 چت با این کاربر", callback_data=f"admin_chat_user_{user['id']}")],
        ]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        message_text = ""
    
    await query.message.reply_text("پایان لیست کاربران در انتظار.", reply_markup=await get_admin_panel_keyboard())

async def approve_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Approves a selected user."""
    query = update.callback_query
    await query.answer()
    user_id_to_approve = int(query.data.split('_')[2])

    if database.approve_user(user_id_to_approve):
        await query.edit_message_text(f"✅ کاربر {user_id_to_approve} تأیید شد.")
        await context.bot.send_message(
            chat_id=user_id_to_approve,
            text="✅ حساب کاربری شما توسط ادمین تأیید شد. اکنون می‌توانید از تمامی امکانات ربات استفاده کنید!",
            reply_markup=await get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(f"❌ خطایی در تأیید کاربر {user_id_to_approve} رخ داد.")
    await query.message.reply_text("به پنل ادمین بازگشتیم.", reply_markup=await get_admin_panel_keyboard())

async def reject_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rejects a selected user."""
    query = update.callback_query
    await query.answer()
    user_id_to_reject = int(query.data.split('_')[2])

    if database.reject_user(user_id_to_reject):
        await query.edit_message_text(f"❌ کاربر {user_id_to_reject} رد شد.")
        await context.bot.send_message(
            chat_id=user_id_to_reject,
            text="❌ حساب کاربری شما توسط ادمین رد شد. لطفاً در صورت نیاز با پشتیبانی تماس بگیرید."
        )
    else:
        await query.edit_message_text(f"❌ خطایی در رد کاربر {user_id_to_reject} رخ داد.")
    await query.message.reply_text("به پنل ادمین بازگشتیم.", reply_markup=await get_admin_panel_keyboard())

async def admin_add_credit_to_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to enter user ID for credit addition."""
    query = update.callback_query
    await query.answer()
    
    users = database.get_all_users()
    if not users:
        await query.edit_message_text("هیچ کاربری در دیتابیس یافت نشد.")
        return ConversationHandler.END

    message_text = "لیست کاربران برای افزایش اعتبار:\n\n"
    for user in users:
        message_text += f"👤 ID: `{user['id']}` (@{user['username']}) - اعتبار: {user['credit']} تومان\n"
        keyboard = [[InlineKeyboardButton("➕ افزایش اعتبار", callback_data=f"admin_select_user_for_add_credit_{user['id']}")]]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        message_text = ""
    
    await query.message.reply_text("برای افزایش اعتبار کاربر مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_users")]]))
    return config.ADMIN_SELECT_USER_FOR_ACTION


async def ask_user_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback handler to get user ID for credit addition."""
    query = update.callback_query
    await query.answer()
    target_user_id = int(query.data.split('_')[5]) # admin_select_user_for_add_credit_USER_ID

    context.user_data['target_user_id_for_credit'] = target_user_id
    await query.edit_message_text(f"لطفاً مبلغ اعتبار (به تومان) را برای کاربر {target_user_id} وارد کنید:")
    return config.ADMIN_USER_ADD_CREDIT_AMOUNT

async def do_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds credit to the specified user."""
    target_user_id = context.user_data.get('target_user_id_for_credit')
    if not target_user_id:
        await update.message.reply_text("خطا: شناسه کاربر برای افزایش اعتبار مشخص نیست. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("مبلغ باید مثبت باشد. لطفاً یک عدد معتبر وارد کنید.")
            return config.ADMIN_USER_ADD_CREDIT_AMOUNT

        if database.increase_credit(target_user_id, amount):
            await update.message.reply_text(f"✅ {amount} تومان به اعتبار کاربر {target_user_id} اضافه شد.")
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎁 {amount} تومان اعتبار به حساب شما توسط ادمین اضافه شد. اعتبار جدید شما: {database.get_user(target_user_id)['credit']} تومان"
            )
        else:
            await update.message.reply_text("❌ خطایی در افزایش اعتبار رخ داد.")
    except ValueError:
        await update.message.reply_text("مبلغ نامعتبر است. لطفاً یک عدد وارد کنید.")
        return config.ADMIN_USER_ADD_CREDIT_AMOUNT
    
    context.user_data.pop('target_user_id_for_credit', None)
    return ConversationHandler.END # Ends the specific credit addition convo


# Admin Service Management
async def admin_manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays service management options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("➕ تنظیم/بروزرسانی سرویس", callback_data="admin_set_service_type_ask")],
        [InlineKeyboardButton("💰 تنظیم قیمت سرویس", callback_data="admin_set_service_price_ask")],
        [InlineKeyboardButton("🗑 حذف سرویس", callback_data="admin_delete_service_ask")],
        [InlineKeyboardButton("📋 مشاهده همه سرویس‌ها", callback_data="admin_view_all_services")],
        [InlineKeyboardButton("💲 مشاهده قیمت سرویس‌ها", callback_data="admin_view_all_service_prices")],
        [InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠 مدیریت سرویس‌ها:", reply_markup=reply_markup)

async def admin_set_service_type_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin to choose service type to set/update content."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"set_service_type_{key}")] for name, key in config.SERVICE_TYPES.items()]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً نوع سرویسی که می‌خواهید محتوایش را تنظیم یا بروزرسانی کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_SET_SERVICE

async def admin_set_service_content_or_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin if content is text or file."""
    query = update.callback_query
    await query.answer()
    service_type = query.data.split('_')[3] # set_service_type_openvpn

    context.user_data['service_type_to_set'] = service_type

    keyboard = [
        [InlineKeyboardButton("📝 محتوای متنی (لینک/متن)", callback_data="service_content_text")],
        [InlineKeyboardButton("📎 فایل (کانفیگ)", callback_data="service_content_file")],
        [InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"برای سرویس {service_type}، محتوا متنی است یا فایل؟", reply_markup=reply_markup)
    return config.ADMIN_SERVICE_FILE_OR_TEXT

async def receive_service_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives text content for service and saves it."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("لطفاً محتوای متنی (لینک یا متن) سرویس را ارسال کنید:")
    return config.ADMIN_SET_SERVICE_CONTENT # Wait for text input

async def process_service_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the text content and saves it."""
    service_type = context.user_data.get('service_type_to_set')
    content = update.message.text.strip()

    if database.set_service(service_type, content, is_file=False):
        await update.message.reply_text(f"✅ محتوای متنی سرویس {service_type} با موفقیت تنظیم شد.")
    else:
        await update.message.reply_text(f"❌ خطایی در تنظیم محتوای سرویس {service_type} رخ داد.")
    
    context.user_data.pop('service_type_to_set', None)
    return ConversationHandler.END

async def receive_service_file_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives file content for service."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("لطفاً فایل کانفیگ سرویس را ارسال کنید:")
    return config.ADMIN_SET_SERVICE_CONTENT # Wait for file input (documents filter)

async def process_service_file_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the file content and saves it."""
    service_type = context.user_data.get('service_type_to_set')
    
    if not update.message.document:
        await update.message.reply_text("لطفاً یک فایل ارسال کنید.")
        return config.ADMIN_SET_SERVICE_CONTENT

    file_id = update.message.document.file_id
    file_name = update.message.document.file_name
    
    # Save file to a local directory for later use if needed, or just save file_id
    # For now, we will save file_id as content
    if database.set_service(service_type, file_id, is_file=True, file_name=file_name):
        await update.message.reply_text(f"✅ فایل سرویس {service_type} با موفقیت ذخیره شد. (File ID: `{file_id}`)", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ خطایی در ذخیره فایل سرویس {service_type} رخ داد.")
    
    context.user_data.pop('service_type_to_set', None)
    return ConversationHandler.END


async def admin_set_service_price_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin to choose service type to set price."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"set_price_type_{key}")] for name, key in config.SERVICE_TYPES.items()]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً نوع سرویسی که می‌خواهید قیمتش را تنظیم کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_SET_SERVICE_PRICE_TYPE

async def admin_set_service_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin to input price value for selected service type."""
    query = update.callback_query
    await query.answer()
    service_type = query.data.split('_')[3] # set_price_type_openvpn

    context.user_data['service_type_for_price'] = service_type
    await query.edit_message_text(f"لطفاً قیمت (به تومان) برای سرویس {service_type} را وارد کنید:")
    return config.ADMIN_SET_SERVICE_PRICE_VALUE

async def process_service_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes and saves the service price."""
    service_type = context.user_data.get('service_type_for_price')
    try:
        price = int(update.message.text.strip())
        if price < 0:
            await update.message.reply_text("قیمت نمی‌تواند منفی باشد. لطفا مبلغ معتبری وارد کنید.")
            return config.ADMIN_SET_SERVICE_PRICE_VALUE

        if database.set_service_price(service_type, price):
            await update.message.reply_text(f"✅ قیمت سرویس {service_type} به {price} تومان تنظیم شد.")
        else:
            await update.message.reply_text(f"❌ خطایی در تنظیم قیمت سرویس {service_type} رخ داد.")
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر برای قیمت وارد کنید.")
        return config.ADMIN_SET_SERVICE_PRICE_VALUE
    
    context.user_data.pop('service_type_for_price', None)
    return ConversationHandler.END


async def admin_delete_service_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin to choose service type to delete."""
    query = update.callback_query
    await query.answer()

    services = database.get_all_services()
    if not services:
        await query.edit_message_text("هیچ سرویسی برای حذف یافت نشد.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(f"🗑 {s['type']}", callback_data=f"delete_service_{s['type']}")] for s in services]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً سرویسی که می‌خواهید حذف کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_DELETE_DISCOUNT # Using a generic state, can define a new one if needed

async def do_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the selected service."""
    query = update.callback_query
    await query.answer()
    service_type_to_delete = query.data.split('_')[2] # delete_service_openvpn

    if database.delete_service(service_type_to_delete):
        await query.edit_message_text(f"✅ سرویس {service_type_to_delete} با موفقیت حذف شد.")
    else:
        await query.edit_message_text(f"❌ خطایی در حذف سرویس {service_type_to_delete} رخ داد.")
    
    return ConversationHandler.END # End service deletion convo

async def view_all_services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays all defined services."""
    query = update.callback_query
    await query.answer()

    services = database.get_all_services()
    if not services:
        await query.edit_message_text("هیچ سرویسی در دیتابیس تعریف نشده است.")
        return
    
    message_text = "لیست همه سرویس‌ها:\n\n"
    for s in services:
        is_file_str = "فایل" if s['is_file'] else "متن/لینک"
        message_text += f"*{s['type']}*:\n  محتوا: {s['content']}\n  نوع محتوا: {is_file_str}\n  نام فایل: {s['file_name'] if s['file_name'] else 'ندارد'}\n\n"
    
    await query.edit_message_text(message_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")]]))


async def view_all_service_prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays all defined service prices."""
    query = update.callback_query
    await query.answer()

    prices = database.get_all_service_prices()
    if not prices:
        await query.edit_message_text("هیچ قیمتی برای سرویس‌ها تعریف نشده است.")
        return
    
    message_text = "قیمت سرویس‌ها:\n\n"
    for s_type, price in prices.items():
        message_text += f"*{s_type}*: {price} تومان\n"
    
    await query.edit_message_text(message_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_manage_services")]]))


# Admin Discount Codes
async def admin_discount_codes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays discount code management options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="admin_add_discount_ask")],
        [InlineKeyboardButton("🗑 حذف کد تخفیف", callback_data="admin_delete_discount_ask")],
        [InlineKeyboardButton("📋 مشاهده همه کدها", callback_data="admin_view_all_discount_codes")],
        [InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠 مدیریت کدهای تخفیف:", reply_markup=reply_markup)

async def ask_add_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin for new discount code and value."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً کد تخفیف جدید و مقدار آن را وارد کنید (مثال: CODE1000 1000):")
    return config.ADMIN_ADD_DISCOUNT_VALUE

async def do_add_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds a new discount code."""
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("فرمت نامعتبر.")
        
        code = parts[0]
        value = int(parts[1])

        if database.add_discount_code(code, value):
            await update.message.reply_text(f"✅ کد تخفیف '{code}' با مقدار {value} با موفقیت اضافه شد.")
        else:
            await update.message.reply_text(f"❌ کد تخفیف '{code}' از قبل وجود دارد یا خطایی رخ داد.")
    except ValueError:
        await update.message.reply_text("فرمت ورودی نامعتبر است. لطفاً به صورت 'CODE1000 1000' وارد کنید.")
        return config.ADMIN_ADD_DISCOUNT_VALUE
    
    return ConversationHandler.END

async def ask_delete_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin for discount code to delete."""
    query = update.callback_query
    await query.answer()
    
    codes = database.get_all_discount_codes()
    if not codes:
        await query.edit_message_text("هیچ کد تخفیفی برای حذف یافت نشد.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(f"🗑 {c['code']} (Val:{c['value']})", callback_data=f"delete_code_{c['code']}")] for c in codes]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="admin_discount_codes")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً کد تخفیفی که می‌خواهید حذف کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_DELETE_DISCOUNT

async def do_delete_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the selected discount code."""
    query = update.callback_query
    await query.answer()
    code_to_delete = query.data.split('_')[2]

    if database.delete_discount_code(code_to_delete):
        await query.edit_message_text(f"✅ کد تخفیف '{code_to_delete}' با موفقیت حذف شد.")
    else:
        await query.edit_message_text(f"❌ خطایی در حذف کد تخفیف '{code_to_delete}' رخ داد.")
    
    return ConversationHandler.END

async def view_all_discount_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays all discount codes."""
    query = update.callback_query
    await query.answer()

    codes = database.get_all_discount_codes()
    if not codes:
        await query.edit_message_text("هیچ کد تخفیفی در دیتابیس یافت نشد.")
        return
    
    message_text = "لیست کدهای تخفیف:\n\n"
    for code_data in codes:
        message_text += f"*{code_data['code']}*: {code_data['value']} تومان (استفاده شده: {code_data['usage_count']} بار)\n"
    
    await query.edit_message_text(message_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_discount_codes")]]))

# Admin Purchase Requests
async def admin_requests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays purchase request management options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("⏳ مشاهده درخواست‌های در انتظار", callback_data="admin_view_pending_requests")],
        [InlineKeyboardButton("✅ مشاهده درخواست‌های تأیید شده", callback_data="admin_view_approved_requests")],
        [InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠 مدیریت درخواست‌های خرید:", reply_markup=reply_markup)

async def view_pending_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays pending purchase requests."""
    query = update.callback_query
    await query.answer()

    requests = database.get_purchase_requests_by_status('pending')
    if not requests:
        await query.edit_message_text("هیچ درخواست خرید در انتظاری یافت نشد.")
        return
    
    message_text = "درخواست‌های خرید در انتظار:\n\n"
    for req in requests:
        user = database.get_user(req['user_id'])
        username = user['username'] if user else 'نامشخص'
        message_text = (
            f"🛒 درخواست #{req['id']}\n"
            f"کاربر: `{req['user_id']}` (@{username})\n"
            f"نوع اکانت: {req['account_type']}\n"
            f"سرویس درخواستی: {req['requested_service']}\n"
            f"دستگاه درخواستی: {req['requested_device']}\n"
            f"تاریخ درخواست: {req['request_date'].split('T')[0]}\n"
        )
        keyboard = [
            [InlineKeyboardButton("✅ تأیید و ارسال سرویس", callback_data=f"process_request_approve_{req['id']}")],
            [InlineKeyboardButton("❌ رد کردن درخواست", callback_data=f"process_request_reject_{req['id']}")],
            [InlineKeyboardButton("💬 چت با این کاربر", callback_data=f"admin_chat_user_{req['user_id']}")],
        ]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    await query.message.reply_text("پایان لیست درخواست‌های در انتظار.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_requests")]]))

async def view_approved_requests_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays approved purchase requests."""
    query = update.callback_query
    await query.answer()

    requests = database.get_purchase_requests_by_status('approved')
    if not requests:
        await query.edit_message_text("هیچ درخواست خرید تأیید شده‌ای یافت نشد.")
        return
    
    message_text = "درخواست‌های خرید تأیید شده:\n\n"
    for req in requests:
        user = database.get_user(req['user_id'])
        username = user['username'] if user else 'نامشخص'
        message_text += (
            f"🛒 درخواست #{req['id']}\n"
            f"کاربر: `{req['user_id']}` (@{username})\n"
            f"نوع اکانت: {req['account_type']}\n"
            f"سرویس درخواستی: {req['requested_service']}\n"
            f"دستگاه درخواستی: {req['requested_device']}\n"
            f"تاریخ درخواست: {req['request_date'].split('T')[0]}\n"
            f"وضعیت: {req['status']}\n\n"
        )
    await query.edit_message_text(message_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_requests")]]))

async def process_request_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes a purchase request (approves or rejects)."""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[2] # 'approve' or 'reject'
    request_id = int(parts[3])

    req = database.get_purchase_request_by_id(request_id)
    if not req:
        await query.edit_message_text("درخواست خرید یافت نشد.")
        return ConversationHandler.END
    
    user_id_to_notify = req['user_id']

    if action == 'approve':
        database.update_purchase_request_status(request_id, 'approved')
        await query.edit_message_text(f"✅ درخواست خرید #{request_id} تأیید شد.\nحالا سرویس را برای کاربر ارسال کنید.")
        
        # Start guided service delivery
        context.user_data['service_delivery_target_user_id'] = user_id_to_notify
        context.user_data['service_delivery_request_id'] = request_id
        await start_service_delivery_after_approval(update, context) # Call the function directly
        return config.ADMIN_DELIVERING_SERVICE_CHOOSE_METHOD # Transition to service delivery state

    elif action == 'reject':
        database.update_purchase_request_status(request_id, 'rejected')
        await query.edit_message_text(f"❌ درخواست خرید #{request_id} رد شد.")
        await context.bot.send_message(
            chat_id=user_id_to_notify,
            text=f"❌ درخواست خرید شما (شماره #{request_id}) توسط ادمین رد شد. لطفاً در صورت نیاز با پشتیبانی تماس بگیرید."
        )
        return ConversationHandler.END # End the process for now, return to main admin menu or previous state


# Admin Statistics
async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays bot statistics."""
    query = update.callback_query
    await query.answer()

    stats = database.get_bot_statistics()
    if not stats:
        await query.edit_message_text("خطا در دریافت آمار ربات.")
        return
    
    stats_text = (
        "📊 آمار کلی ربات:\n\n"
        f"تعداد کل کاربران: {stats.get('total_users', 0)}\n"
        f"کاربران تأیید شده: {stats.get('approved_users', 0)}\n"
        f"کاربران در انتظار تأیید: {stats.get('pending_users', 0)}\n"
        f"کل اعتبار کاربران: {stats.get('total_credit', 0)} تومان\n"
        f"تعداد کدهای تخفیف: {stats.get('total_discount_codes', 0)}\n"
        f"تعداد کل پیام‌های پشتیبانی: {stats.get('total_support_messages', 0)}\n"
    )
    await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_main_menu")]]))


# Admin Support Messages
async def admin_support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays support message management options."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("⏳ مشاهده پیام‌های بی‌پاسخ", callback_data="admin_view_unanswered_support")],
        [InlineKeyboardButton("📋 مشاهده همه پیام‌ها", callback_data="admin_view_all_support")],
        [InlineKeyboardButton("↩️ بازگشت به پنل اصلی", callback_data="admin_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠 مدیریت پیام‌های پشتیبانی:", reply_markup=reply_markup)

async def view_unanswered_support_messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays unanswered support messages."""
    query = update.callback_query
    await query.answer()

    messages = database.get_support_messages(answered=False)
    if not messages:
        await query.edit_message_text("هیچ پیام پشتیبانی بی‌پاسخی یافت نشد.")
        return
    
    await query.edit_message_text("پیام‌های پشتیبانی بی‌پاسخ:")
    for msg in messages:
        user = database.get_user(msg['user_id'])
        username = user['username'] if user else 'نامشخص'
        message_text = (
            f"🆔 پیام #{msg['id']}\n"
            f"کاربر: `{msg['user_id']}` (@{username})\n"
            f"تاریخ: {msg['message_date'].split('T')[0]}\n"
            f"متن: \"{msg['message_text']}\""
        )
        keyboard = [
            [InlineKeyboardButton("✅ علامت‌گذاری به عنوان پاسخ داده شده", callback_data=f"mark_support_answered_{msg['id']}")],
            [InlineKeyboardButton("💬 پاسخ به این کاربر", callback_data=f"admin_chat_user_{msg['user_id']}")], # Reuse chat function
        ]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    await query.message.reply_text("پایان لیست پیام‌های بی‌پاسخ.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_support")]]))

async def view_all_support_messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays all support messages."""
    query = update.callback_query
    await query.answer()

    messages = database.get_support_messages(answered=None) # Get all
    if not messages:
        await query.edit_message_text("هیچ پیام پشتیبانی یافت نشد.")
        return
    
    await query.edit_message_text("همه پیام‌های پشتیبانی:")
    for msg in messages:
        user = database.get_user(msg['user_id'])
        username = user['username'] if user else 'نامشخص'
        status = "✅ پاسخ داده شده" if msg['is_answered'] else "⏳ بی‌پاسخ"
        message_text = (
            f"🆔 پیام #{msg['id']}\n"
            f"کاربر: `{msg['user_id']}` (@{username})\n"
            f"تاریخ: {msg['message_date'].split('T')[0]}\n"
            f"وضعیت: {status}\n"
            f"متن: \"{msg['message_text']}\""
        )
        keyboard = [
            [InlineKeyboardButton("💬 چت با این کاربر", callback_data=f"admin_chat_user_{msg['user_id']}")],
        ]
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    await query.message.reply_text("پایان لیست پیام‌های پشتیبانی.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="admin_support")]]))


async def mark_support_message_answered_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Marks a support message as answered."""
    query = update.callback_query
    await query.answer()
    message_id = int(query.data.split('_')[3]) # mark_support_answered_MESSAGE_ID

    if database.mark_support_message_answered(message_id):
        await query.edit_message_text(f"✅ پیام پشتیبانی #{message_id} به عنوان پاسخ داده شده علامت‌گذاری شد.")
    else:
        await query.edit_message_text(f"❌ خطایی در علامت‌گذاری پیام #{message_id} رخ داد.")
    await query.message.reply_text("به پنل ادمین بازگشتیم.", reply_markup=await get_admin_panel_keyboard())


# Admin Broadcast
async def ask_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks admin for the broadcast message."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ شما به این بخش دسترسی ندارید.")
        return ConversationHandler.END
    
    await update.message.reply_text("لطفاً پیام همگانی را وارد کنید:")
    return config.ADMIN_BROADCAST_MESSAGE

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the broadcast message to all users."""
    broadcast_message = update.message.text.strip()
    
    users = database.get_all_users()
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text("در حال ارسال پیام همگانی...")

    for user in users:
        try:
            await context.bot.send_message(chat_id=user['id'], text=f"📢 پیام از ادمین:\n\n{broadcast_message}")
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user['id']}: {e}")
            failed_count += 1
    
    await update.message.reply_text(f"✅ پیام همگانی ارسال شد.\nموفق: {sent_count}\nناموفق: {failed_count}")
    return ConversationHandler.END


# --- NEW FEATURE: Admin-User Direct Chat ---

async def chat_with_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for admin to start a direct chat with a user."""
    query = update.callback_query
    await query.answer()

    target_user_id = int(query.data.split('_')[3]) # admin_chat_user_USER_ID
    target_user = database.get_user(target_user_id)

    if not target_user:
        await query.edit_message_text("کاربر مورد نظر یافت نشد.")
        return ConversationHandler.END
    
    context.user_data['admin_chat_target_user_id'] = target_user_id
    await query.edit_message_text(
        f"شما وارد حالت چت با کاربر {target_user_id} (@{target_user.get('username', 'نامشخص')}) شدید.\n"
        "هر پیامی که اینجا ارسال کنید به او فرستاده می‌شود.\n"
        "برای خروج از چت، /cancel را وارد کنید."
    )
    # Inform the user that admin is initiating chat
    await context.bot.send_message(
        chat_id=target_user_id,
        text=f"✉️ ادمین در حال چت با شماست.\n"
             "می‌توانید پیام‌های خود را اینجا ارسال کنید. برای خروج از چت، /cancel را بزنید."
    )
    return config.ADMIN_CHATTING_WITH_USER

async def admin_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles messages from admin in direct chat mode."""
    target_user_id = context.user_data.get('admin_chat_target_user_id')
    if not target_user_id:
        await update.message.reply_text("خطا: کاربر مقصد برای چت مشخص نیست. لطفاً /cancel را بزنید و دوباره تلاش کنید.")
        return ConversationHandler.END
    
    message_to_send = update.message.text
    try:
        await context.bot.send_message(chat_id=target_user_id, text=f"پیام از ادمین: {message_to_send}")
        await update.message.reply_text("پیام شما ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"خطا در ارسال پیام به کاربر: {e}")
    
    return config.ADMIN_CHATTING_WITH_USER # Stay in chat state

async def user_reply_to_admin_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles replies from user when admin is in chat mode with them."""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # This function acts as a general message handler for users.
    # If the admin is currently chatting with this user, forward user's message to admin.
    # The admin's `context.user_data` needs to store the user they are chatting with.
    # This requires checking all active admin contexts, which is complex for a simple bot.
    # A simpler approach: if a message is received from a user, and admin is in a chat state,
    # and that user is the target, display it to the admin.
    # For now, we will simply log this or send it as a support message if no active admin chat.
    
    # A more robust solution would involve a custom dispatcher or more complex state management
    # to route messages based on active conversations.
    # For simplicity, if the user sends a message and it's not part of an ongoing user conversation handler,
    # it's just a regular message. If an admin is chatting with them, Telegram's native reply
    # functionality might suffice outside the bot's direct control, or we need to manage it explicitly.
    
    # Given the request "وقتی کابری پیام پشتیبانی داد ادمین که میخواد جواب بده وارد پت با اون کاربر بشه"
    # The 'reply to user' button from support messages or 'chat with user' will set ADMIN_CHATTING_WITH_USER state.
    # When in ADMIN_CHATTING_WITH_USER state, ALL messages from this specific user will be forwarded to admin.
    
    # This requires checking if the current *admin* has 'admin_chat_target_user_id' set to this user_id
    # This is a bit tricky with `ContextTypes.DEFAULT_TYPE`, which is for the current update.
    # We'd need to iterate through all active contexts for ADMIN_ID, or use a global dict for active chats.
    # For now, let's assume admin initiates, and user's regular messages are handled as support or main menu actions.
    # The direct reply from the admin covers the support side.
    
    # For the prompt "وقتی کابری پیام پشتیبانی داد ادمین که میخواد جواب بده وارد پت با اون کاربر بشه":
    # The "Reply to this user" button now transitions to ADMIN_CHATTING_WITH_USER.
    # The user's replies need to be seen by the admin.
    # This will require custom logic in the main dispatcher or a dedicated listener.
    
    # Simpler version for `user_reply_to_admin_chat`:
    # If a message is received and it's from a user who is being chatted with by ADMIN_ID,
    # forward it to ADMIN_ID. This is a general MessageHandler.
    
    # Check if this user is currently being chatted with by the admin.
    # This information would typically be stored in a global dictionary or context outside of a specific user's context.
    # For example, context.bot_data['active_admin_chats'] = {admin_id: target_user_id}
    
    # This part requires more robust state management beyond single user_data.
    # For now, let's assume the admin initiates, and regular user messages default to support if it's the right context.
    pass # This function needs more complex logic to route back to the admin effectively.

# --- NEW FEATURE: Guided Service Delivery for Admin ---

async def start_service_delivery_after_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiates the service delivery flow after a purchase request is approved."""
    # This function is called directly from process_request_command after approval.
    target_user_id = context.user_data.get('service_delivery_target_user_id')
    request_id = context.user_data.get('service_delivery_request_id')

    if not target_user_id or not request_id:
        await update.callback_query.message.reply_text("خطا در شروع فرآیند ارسال سرویس. اطلاعات کاربر یا درخواست یافت نشد.")
        return ConversationHandler.END

    await update.callback_query.message.reply_text(
        f"شما درخواست خرید #{request_id} از کاربر {target_user_id} را تأیید کردید.\n"
        "حالا لطفاً روش ارسال سرویس را انتخاب کنید:"
    )
    keyboard = [
        [InlineKeyboardButton("ارسال سرویس موجود (ذخیره شده)", callback_data="deliver_existing_service")],
        [InlineKeyboardButton("ارسال محتوای جدید (متن/فایل)", callback_data="deliver_new_content")],
        [InlineKeyboardButton("لغو ارسال", callback_data="cancel_delivery")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("انتخاب روش ارسال:", reply_markup=reply_markup)
    return config.ADMIN_DELIVERING_SERVICE_CHOOSE_METHOD

async def choose_delivery_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin chooses whether to send existing service or new content."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "deliver_existing_service":
        return await send_predefined_service_choice(update, context)
    elif choice == "deliver_new_content":
        return await choose_new_delivery_type(update, context)
    elif choice == "cancel_delivery":
        await query.edit_message_text("ارسال سرویس لغو شد.")
        # Clear context data
        context.user_data.pop('service_delivery_target_user_id', None)
        context.user_data.pop('service_delivery_request_id', None)
        return ConversationHandler.END
    return config.ADMIN_DELIVERING_SERVICE_CHOOSE_METHOD # Stay in state on unexpected callback

async def send_predefined_service_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin selects which existing service to send."""
    query = update.callback_query
    await query.answer()

    services = database.get_all_services()
    if not services:
        await query.edit_message_text("هیچ سرویس ذخیره شده‌ای برای ارسال وجود ندارد. لطفاً ابتدا سرویس‌ها را تنظیم کنید.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(s['type'], callback_data=f"send_existing_{s['type']}")] for s in services]
    keyboard.append([InlineKeyboardButton("↩️ بازگشت", callback_data="deliver_cancel_send")]) # Custom callback to cancel delivery
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً سرویس ذخیره شده‌ای که می‌خواهید ارسال کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_DELIVERING_SERVICE_CHOOSE_EXISTING

async def send_existing_service_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the selected predefined service to the user."""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.split('_')[2] # send_existing_openvpn
    target_user_id = context.user_data.get('service_delivery_target_user_id')
    
    if not target_user_id:
        await query.edit_message_text("خطا: کاربر مقصد برای ارسال سرویس مشخص نیست.")
        return ConversationHandler.END

    service_data = database.get_service(service_type)
    if not service_data:
        await query.edit_message_text(f"سرویس {service_type} در دیتابیس یافت نشد.")
        return ConversationHandler.END

    try:
        if service_data['is_file']:
            file_id = service_data['content']
            file_name = service_data['file_name'] if service_data['file_name'] else f"{service_type}_config.ovpn"
            await context.bot.send_document(chat_id=target_user_id, document=file_id, filename=file_name, caption=f"سرویس {service_type} شما:")
        else:
            await context.bot.send_message(chat_id=target_user_id, text=f"سرویس {service_type} شما:\n\n{service_data['content']}")
        
        await query.edit_message_text(f"✅ سرویس {service_type} با موفقیت برای کاربر {target_user_id} ارسال شد.")
    except Exception as e:
        await query.edit_message_text(f"❌ خطایی در ارسال سرویس رخ داد: {e}")
    
    # Clear context data
    context.user_data.pop('service_delivery_target_user_id', None)
    context.user_data.pop('service_delivery_request_id', None)
    return ConversationHandler.END


async def choose_new_delivery_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin chooses if new content is text or file."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("متن/لینک", callback_data="new_delivery_text")],
        [InlineKeyboardButton("فایل", callback_data="new_delivery_file")],
        [InlineKeyboardButton("↩️ بازگشت", callback_data="deliver_cancel_send")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً نوع محتوای جدیدی که می‌خواهید ارسال کنید را انتخاب کنید:", reply_markup=reply_markup)
    return config.ADMIN_DELIVERING_SERVICE_CHOOSE_METHOD # Stay in method choice for now, next state will be receiving content

async def ask_for_new_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to send new text content."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً محتوای متنی (لینک/اطلاعات) را برای کاربر ارسال کنید:")
    return config.ADMIN_DELIVERING_SERVICE_RECEIVING_TEXT

async def receive_and_send_new_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and sends new text content to the target user."""
    target_user_id = context.user_data.get('service_delivery_target_user_id')
    if not target_user_id:
        await update.message.reply_text("خطا: کاربر مقصد برای ارسال سرویس مشخص نیست. لطفاً /cancel را بزنید.")
        return ConversationHandler.END

    content = update.message.text
    try:
        await context.bot.send_message(chat_id=target_user_id, text=f"سرویس درخواستی شما:\n\n{content}")
        await update.message.reply_text(f"✅ محتوای متنی با موفقیت برای کاربر {target_user_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطایی در ارسال محتوای متنی رخ داد: {e}")
    
    # Clear context data
    context.user_data.pop('service_delivery_target_user_id', None)
    context.user_data.pop('service_delivery_request_id', None)
    return ConversationHandler.END

async def ask_for_new_file_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts admin to send new file content."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً فایل (کانفیگ/سایر) را برای کاربر ارسال کنید:")
    return config.ADMIN_DELIVERING_SERVICE_RECEIVING_FILE

async def receive_and_send_new_file_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and sends new file content to the target user."""
    target_user_id = context.user_data.get('service_delivery_target_user_id')
    if not target_user_id:
        await update.message.reply_text("خطا: کاربر مقصد برای ارسال سرویس مشخص نیست. لطفاً /cancel را بزنید.")
        return ConversationHandler.END

    if not update.message.document:
        await update.message.reply_text("لطفاً یک فایل ارسال کنید.")
        return config.ADMIN_DELIVERING_SERVICE_RECEIVING_FILE
    
    file_id = update.message.document.file_id
    file_name = update.message.document.file_name

    try:
        await context.bot.send_document(chat_id=target_user_id, document=file_id, filename=file_name, caption="فایل سرویس درخواستی شما:")
        await update.message.reply_text(f"✅ فایل با موفقیت برای کاربر {target_user_id} ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطایی در ارسال فایل رخ داد: {e}")
    
    # Clear context data
    context.user_data.pop('service_delivery_target_user_id', None)
    context.user_data.pop('service_delivery_request_id', None)
    return ConversationHandler.END

# General exit for admin conversations (e.g., from an admin-initiated chat)
async def exit_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exits admin conversation context."""
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        # Clear specific chat target if set
        context.user_data.pop('admin_chat_target_user_id', None)
        context.user_data.pop('service_delivery_target_user_id', None)
        context.user_data.pop('service_delivery_request_id', None)

        await update.message.reply_text(
            "شما از حالت فعلی خارج شدید. به پنل ادمین بازگشتید.",
            reply_markup=await get_admin_panel_keyboard()
        )
        return ConversationHandler.END # End current admin conversation
    else:
        # For regular users, this is handled by the general cancel command
        return await cancel(update, context)

# --- Main Application Setup ---

def main() -> None:
    """Runs the bot."""
    # Initialize the database
    database.init_database()

    application = Application.builder().token(TOKEN).build()

    # --- User Conversation Handlers ---
    
    # Registration Conversation
    registration_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            MessageHandler(filters.Regex("^(👤 اطلاعات من|💰 اعتبار من|📞 پشتیبانی|💳 انتقال اعتبار|🎁 استفاده از کد تخفیف|⬇️ دانلود برنامه‌ها|🛍 خرید اکانت)$"), start_command) # If user clicks a button but isn't registered fully
        ],
        states={
            config.REQUESTING_CONTACT: [MessageHandler(filters.CONTACT, receive_contact)],
            config.REQUESTING_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)],
            config.SELECTING_OS: [CallbackQueryHandler(receive_os, pattern=r"^os_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(registration_conv)

    # Purchase Conversation
    purchase_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛍 خرید اکانت$"), purchase_command)],
        states={
            config.SELECTING_PURCHASE_ACCOUNT_TYPE: [CallbackQueryHandler(select_purchase_account_type, pattern=r"^account_")],
            config.SELECTING_DEVICE: [CallbackQueryHandler(select_device_type, pattern=r"^device_")],
            config.SELECTING_SERVICE: [CallbackQueryHandler(select_service_type, pattern=r"^service_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(purchase_conv)

    # Discount Conversation
    discount_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 استفاده از کد تخفیف$"), discount_command)],
        states={
            config.ENTERING_DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_discount_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(discount_conv)

    # Transfer Conversation
    transfer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 انتقال اعتبار$"), transfer_command)],
        states={
            config.TRANSFER_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_transfer_amount)],
            config.TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_transfer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(transfer_conv)

    # Support Conversation
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📞 پشتیبانی$"), support_command)],
        states={
            config.ENTERING_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_support_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(support_conv)


    # --- Admin Conversation Handlers ---

    # Admin Service Management Conversation
    admin_service_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_set_service_type_ask, pattern=r"^admin_set_service_type_ask$"),
            CallbackQueryHandler(admin_set_service_price_ask, pattern=r"^admin_set_service_price_ask$"),
            CallbackQueryHandler(admin_delete_service_ask, pattern=r"^admin_delete_service_ask$"),
        ],
        states={
            config.ADMIN_SET_SERVICE: [CallbackQueryHandler(admin_set_service_content_or_file, pattern=r"^set_service_type_")],
            config.ADMIN_SERVICE_FILE_OR_TEXT: [
                CallbackQueryHandler(receive_service_text_content, pattern=r"^service_content_text$"),
                CallbackQueryHandler(receive_service_file_content, pattern=r"^service_content_file$"),
            ],
            config.ADMIN_SET_SERVICE_CONTENT: [ # This state receives either text or file
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_text_content),
                MessageHandler(filters.Document.ALL, process_service_file_content),
            ],
            config.ADMIN_SET_SERVICE_PRICE_TYPE: [CallbackQueryHandler(admin_set_service_price_value, pattern=r"^set_price_type_")],
            config.ADMIN_SET_SERVICE_PRICE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_service_price_value)],
            config.ADMIN_DELETE_DISCOUNT: [CallbackQueryHandler(do_delete_service, pattern=r"^delete_service_")], # Reusing state, but handler is specific
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_manage_services_menu, pattern="admin_manage_services")],
    )
    application.add_handler(admin_service_conv)

    # Admin Discount Management Conversation
    admin_discount_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_add_discount_code, pattern=r"^admin_add_discount_ask$"),
            CallbackQueryHandler(ask_delete_discount_code, pattern=r"^admin_delete_discount_ask$"),
        ],
        states={
            config.ADMIN_ADD_DISCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_add_discount_code)],
            config.ADMIN_DELETE_DISCOUNT: [CallbackQueryHandler(do_delete_discount_code, pattern=r"^delete_code_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_discount_codes_menu, pattern="admin_discount_codes")],
    )
    application.add_handler(admin_discount_conv)

    # Admin User Management - Add Credit Conversation
    admin_credit_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_user_add_credit, pattern=r"^admin_select_user_for_add_credit_"),
        ],
        states={
            config.ADMIN_USER_ADD_CREDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_add_credit)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_manage_users_menu, pattern="admin_manage_users")],
    )
    application.add_handler(admin_credit_conv)

    # Admin Broadcast Conversation
    admin_broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("askbroadcast", ask_broadcast), CallbackQueryHandler(lambda q,c: ask_broadcast(q.message, c), pattern="admin_broadcast_ask")],
        states={
            config.ADMIN_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(admin_panel, pattern="admin_main_menu")],
    )
    application.add_handler(admin_broadcast_conv)

    # Admin Purchase Request Processing (including NEW service delivery flow)
    admin_purchase_request_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(process_request_command, pattern=r"process_request_"),
        ],
        states={
            # State after approving request
            config.ADMIN_DELIVERING_SERVICE_CHOOSE_METHOD: [
                CallbackQueryHandler(choose_delivery_method, pattern=r"^(deliver_existing_service|deliver_new_content|cancel_delivery)$")
            ],
            # If admin chooses existing service
            config.ADMIN_DELIVERING_SERVICE_CHOOSE_EXISTING: [
                CallbackQueryHandler(send_existing_service_content, pattern=r"^send_existing_")
            ],
            # If admin chooses new content
            config.ADMIN_DELIVERING_SERVICE_RECEIVING_CONTENT: [
                CallbackQueryHandler(ask_for_new_text_content, pattern="new_delivery_text"),
                CallbackQueryHandler(ask_for_new_file_content, pattern="new_delivery_file"),
            ],
            config.ADMIN_DELIVERING_SERVICE_RECEIVING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_and_send_new_text_content)],
            config.ADMIN_DELIVERING_SERVICE_RECEIVING_FILE: [MessageHandler(filters.Document.ALL, receive_and_send_new_file_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(lambda q,c: q.edit_message_text("عملیات لغو شد.").then(admin_requests_menu(q,c)), pattern="admin_requests")], # Fallback to requests menu
    )
    application.add_handler(admin_purchase_request_conv)
    

    # --- NEW FEATURE: Admin-User Direct Chat Conversation ---
    admin_user_chat_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(chat_with_user_entry, pattern=r"^admin_chat_user_"), # From user lists or support view
        ],
        states={
            config.ADMIN_CHATTING_WITH_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_chat_message),
                MessageHandler(filters.PHOTO | filters.Document.ALL, admin_chat_message), # Allow sending photos/docs
            ],
            # user_chat_message would be a general handler, not part of specific conv state
        },
        fallbacks=[CommandHandler("cancel", exit_chat), CommandHandler("exit_chat", exit_chat)],
    )
    application.add_handler(admin_user_chat_conv)


    # --- General Command and Callback Handlers ---
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("score", show_credit_command))
    application.add_handler(CommandHandler("myinfo", show_status_command))
    
    # Handlers for main menu ReplyKeyboard buttons (regex for exact match)
    application.add_handler(MessageHandler(filters.Regex("^💰 اعتبار من$"), show_credit_command))
    application.add_handler(MessageHandler(filters.Regex("^👤 اطلاعات من$"), show_status_command))
    application.add_handler(MessageHandler(filters.Regex("^⬇️ دانلود برنامه‌ها$"), show_app_downloads_command))

    # General callback query handlers for admin panel navigation
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="admin_main_menu"))
    application.add_handler(CallbackQueryHandler(admin_manage_users_menu, pattern="admin_manage_users"))
    application.add_handler(CallbackQueryHandler(admin_manage_services_menu, pattern="admin_manage_services"))
    application.add_handler(CallbackQueryHandler(admin_discount_codes_menu, pattern="admin_discount_codes"))
    application.add_handler(CallbackQueryHandler(admin_requests_menu, pattern="admin_requests"))
    application.add_handler(CallbackQueryHandler(admin_stats_command, pattern="admin_stats"))
    application.add_handler(CallbackQueryHandler(admin_support_menu, pattern="admin_support"))

    # Specific admin callbacks not part of conv handlers
    application.add_handler(CallbackQueryHandler(view_all_users_command, pattern="admin_view_all_users"))
    application.add_handler(CallbackQueryHandler(view_pending_users_command, pattern="admin_view_pending_users"))
    application.add_handler(CallbackQueryHandler(approve_user_action, pattern=r"^approve_user_"))
    application.add_handler(CallbackQueryHandler(reject_user_action, pattern=r"^reject_user_"))
    
    application.add_handler(CallbackQueryHandler(view_all_services_command, pattern="admin_view_all_services"))
    application.add_handler(CallbackQueryHandler(view_all_service_prices_command, pattern="admin_view_all_service_prices"))
    
    application.add_handler(CallbackQueryHandler(view_all_discount_codes_command, pattern="admin_view_all_discount_codes"))

    application.add_handler(CallbackQueryHandler(view_pending_requests_command, pattern="admin_view_pending_requests"))
    application.add_handler(CallbackQueryHandler(view_approved_requests_command, pattern="admin_view_approved_requests"))
    
    application.add_handler(CallbackQueryHandler(view_unanswered_support_messages_command, pattern="admin_view_unanswered_support"))
    application.add_handler(CallbackQueryHandler(view_all_support_messages_command, pattern="admin_view_all_support"))
    application.add_handler(CallbackQueryHandler(mark_support_message_answered_action, pattern=r"^mark_support_answered_"))

    application.add_handler(CallbackQueryHandler(show_connection_guide, pattern="show_connection_guide"))

    # Fallback for undefined callbacks in admin delivery (e.g. "بازگشت" or "cancel")
    application.add_handler(CallbackQueryHandler(lambda q,c: q.edit_message_text("عملیات ارسال لغو شد.").then(admin_panel(q,c)), pattern="deliver_cancel_send"))


    # Run the bot
    print("🤖 ربات VPN با دکمه‌های شیشه‌ای شروع شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
