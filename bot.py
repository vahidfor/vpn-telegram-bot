import os
import sqlite3
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import database  # Import our database module
import config    # Import our config module
import logging

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

# Initialize database
database.init_database()

# Conversation states (using states from config module and extending for new flows)
# User flow states
(
    REQUESTING_CONTACT, REQUESTING_FULL_NAME, SELECTING_OS,
    SELECTING_ACCOUNT_TYPE, SELECTING_DEVICE, SELECTING_SERVICE, ENTERING_DISCOUNT_CODE,
    ENTERING_SUPPORT_MESSAGE, SENDING_ACCOUNT_DETAILS, SELECTING_PURCHASE_ACCOUNT_TYPE,
    TRANSFER_USER_ID, TRANSFER_AMOUNT
) = range(1, 13) # Start from 1 to avoid conflict with END= -1

# Admin flow states
(
    ADMIN_MAIN_MENU, ADMIN_USERS, ADMIN_SERVICES, ADMIN_APPROVE_USER, ADMIN_REJECT_USER,
    ADMIN_ADD_CREDIT, ADMIN_ADD_CREDIT_AMOUNT, ADMIN_SET_SERVICE, ADMIN_SET_SERVICE_PRICE_TYPE, ADMIN_SET_SERVICE_PRICE_VALUE,
    ADMIN_DISCOUNT_CODES, ADMIN_ADD_DISCOUNT, ADMIN_ADD_DISCOUNT_VALUE, ADMIN_DELETE_DISCOUNT,
    ADMIN_SELECT_USER_FOR_ACTION, ADMIN_CONFIRM_USER_ACTION, ADMIN_TRANSFER_CREDIT_AMOUNT, ADMIN_TRANSFER_CREDIT_TO_USER,
    ADMIN_BROADCAST_MESSAGE, ADMIN_BROADCAST_CONFIRM,
    ADMIN_MANAGE_USERS_MENU, ADMIN_USER_DETAIL_VIEW, ADMIN_USER_ADD_CREDIT_AMOUNT,
    ADMIN_MANAGE_SERVICES_MENU, ADMIN_SET_SERVICE_CONTENT, ADMIN_SERVICE_FILE_OR_TEXT,
    ADMIN_REQUESTS_MENU, ADMIN_VIEW_PENDING_REQUESTS, ADMIN_VIEW_APPROVED_REQUESTS, ADMIN_PROCESS_REQUEST
) = range(100, 131) # Using a higher range to avoid conflict with user states and future expansion

# Helper functions for keyboard markups
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💳 وضعیت اعتبار", callback_data="show_credit")],
        [InlineKeyboardButton("🧾 درخواست سرویس", callback_data="request_service")],
        [InlineKeyboardButton("🔗 سرویس‌های من", callback_data="my_services")],
        [InlineKeyboardButton("💰 انتقال اعتبار", callback_data="transfer_credit")],
        [InlineKeyboardButton("🎁 کد تخفیف", callback_data="apply_discount")],
        [InlineKeyboardButton("❓ راهنما", callback_data="show_help_menu")],
        [InlineKeyboardButton("✉️ پشتیبانی", callback_data="send_support_message")],
        [InlineKeyboardButton("ℹ️ درباره ما", callback_data="about_us")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_manage_users_menu")], # New specific menu
        [InlineKeyboardButton("⚙️ مدیریت سرویس‌ها", callback_data="admin_manage_services_menu")], # New specific menu
        [InlineKeyboardButton("💲 تنظیم قیمت سرویس‌ها", callback_data="admin_set_service_prices")],
        [InlineKeyboardButton("🏷️ مدیریت کدهای تخفیف", callback_data="admin_manage_discounts")],
        [InlineKeyboardButton("📣 پیام همگانی", callback_data="admin_broadcast_message_entry")], # Entry for broadcast
        [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_bot_stats")],
        [InlineKeyboardButton("📝 درخواست‌های خرید", callback_data="admin_manage_purchase_requests")], # New menu for requests
        [InlineKeyboardButton("🚪 خروج از پنل ادمین", callback_data="admin_exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Helper function to get service type keyboard
def get_service_type_keyboard():
    keyboard = []
    for text, data in config.SERVICE_TYPES.items():
        keyboard.append([InlineKeyboardButton(text, callback_data=f"service_{data}")])
    return InlineKeyboardMarkup(keyboard)

# Helper function to get device type keyboard
def get_device_type_keyboard():
    keyboard = []
    for text, data in config.DEVICE_TYPES.items():
        keyboard.append([InlineKeyboardButton(text, callback_data=f"device_{data}")])
    return InlineKeyboardMarkup(keyboard)


# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name

    # Add user to DB if not exists or update basic info. is_approved defaults to 0
    database.add_user(user_id, username, first_name, last_name)
    database.update_user_activity(user_id)

    user = database.get_user(user_id)
    if user and user.get('is_approved'):
        await update.message.reply_text(
            f"سلام {first_name} عزیز! به ربات VPN ما خوش آمدید.",
            reply_markup=get_main_menu_keyboard()
        )
        # Clear any ongoing conversation data for this user if they were stuck
        if 'chat_id' in context.user_data: # If an admin initiated a conversation
             context.user_data.clear()
        return ConversationHandler.END # User is approved, end this specific conversation flow
    else:
        # User is not approved, start the registration process
        await update.message.reply_text(
            "سلام! به ربات VPN خوش آمدید. برای استفاده از خدمات، ابتدا باید اطلاعات شما تایید شود.\n"
            "لطفاً برای ادامه، شماره تماس خود را از طریق دکمه زیر به اشتراک بگذارید:",
            reply_markup=ReplyKeyboardMarkup([[
                KeyboardButton(text="اشتراک گذاری شماره تماس", request_contact=True)
            ]], resize_keyboard=True, one_time_keyboard=True)
        )
        return REQUESTING_CONTACT # Move to the state for requesting contact


# --- User Registration Flow Handlers (for unapproved users) ---

async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    contact = update.message.contact
    phone_number = contact.phone_number

    # Store phone number in user_data for later processing
    context.user_data['phone_number'] = phone_number

    # Update user's phone number in DB
    database.update_user_info(user_id, phone_number=phone_number)
    database.update_user_activity(user_id)

    await update.message.reply_text(
        "از شما متشکرم. لطفاً نام کامل خود را وارد کنید (مثال: علی احمدی):",
        reply_markup=ReplyKeyboardRemove() # Remove the contact sharing keyboard
    )
    return REQUESTING_FULL_NAME # Move to the state for requesting full name

async def receive_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    full_name = update.message.text.strip()

    if not full_name:
        await update.message.reply_text("نام کامل نمی‌تواند خالی باشد. لطفا دوباره وارد کنید:")
        return REQUESTING_FULL_NAME

    # Store full name in user_data
    context.user_data['full_name'] = full_name

    # Update user's full name in DB
    database.update_user_info(user_id, full_name=full_name)
    database.update_user_activity(user_id)

    # Use config.DEVICE_TYPES for OS selection
    keyboard = []
    for text, data in config.DEVICE_TYPES.items():
        if data != "guide": # 'guide' is not a device type to select for registration
            keyboard.append([InlineKeyboardButton(text, callback_data=f"os_select_{data}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "لطفاً سیستم‌عامل دستگاه خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return SELECTING_OS # Move to the state for selecting OS

async def receive_os_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_os = query.data.replace("os_select_", "") # e.g., "android", "ios", "windows"

    # Store selected OS in user_data
    context.user_data['requested_os'] = selected_os

    # Update user's requested OS in DB
    database.update_user_info(user_id, requested_os=selected_os)
    database.update_user_activity(user_id)

    await query.edit_message_text("درخواست شما برای تأیید ارسال شد. لطفاً منتظر تأیید ادمین باشید.")

    # Send notification to admin for approval
    await send_admin_approval_request(user_id, context)

    # Clear user_data for this specific conversation flow
    context.user_data.clear()
    return ConversationHandler.END # End the conversation flow for the user


async def send_admin_approval_request(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    user = database.get_user(user_id)
    if not user:
        logger.error(f"Error: User {user_id} not found when sending admin approval request.")
        return

    message_text = (
        f"درخواست جدید برای تأیید کاربر:\n"
        f"ID: `{user['id']}`\n"
        f"نام کاربری تلگرام: @{user['username']}\n" if user['username'] else f"نام کاربری تلگرام: ندارد\n"
        f"نام کامل: {user.get('full_name', 'نامشخص')}\n"
        f"شماره تماس: {user.get('phone_number', 'نامشخص')}\n"
        f"سیستم‌عامل درخواستی: {user.get('requested_os', 'نامشخص')}\n\n"
        f"تاریخ ثبت‌نام: {user.get('registration_date', 'نامشخص')}"
    )

    keyboard = [[
        InlineKeyboardButton("✅ تأیید کاربر", callback_data=f"admin_approve_user_{user_id}"),
        InlineKeyboardButton("❌ رد کاربر", callback_data=f"admin_reject_user_{user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        logger.info(f"Admin approval request sent for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send admin approval request for user {user_id}: {e}")

# --- Admin Handlers for User Approval ---

async def handle_admin_approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    if admin_id != ADMIN_ID:
        await query.edit_message_text("شما اجازه دسترسی به این عملکرد را ندارید.")
        return

    target_user_id = int(query.data.replace("admin_approve_user_", ""))

    if database.approve_user(target_user_id):
        user = database.get_user(target_user_id)
        if user:
            await query.edit_message_text(f"کاربر `{target_user_id}` با موفقیت تأیید شد.")
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"تبریک! درخواست شما برای عضویت در ربات تأیید شد.\n"
                         f"اکنون می‌توانید از تمام امکانات ربات استفاده کنید.",
                    reply_markup=get_main_menu_keyboard()
                )
                logger.info(f"User {target_user_id} approved and notified.")
            except Exception as e:
                logger.error(f"Failed to notify approved user {target_user_id}: {e}")
        else:
            await query.edit_message_text(f"کاربر `{target_user_id}` تأیید شد اما اطلاعاتش یافت نشد.")
    else:
        await query.edit_message_text(f"خطا در تأیید کاربر `{target_user_id}`.")


async def handle_admin_reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    if admin_id != ADMIN_ID:
        await query.edit_message_text("شما اجازه دسترسی به این عملکرد را ندارید.")
        return

    target_user_id = int(query.data.replace("admin_reject_user_", ""))

    if database.reject_user(target_user_id):
        await query.edit_message_text(f"کاربر `{target_user_id}` رد شد.")
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"متاسفانه درخواست شما برای عضویت در ربات رد شد.\n"
                     f"می‌توانید با ارسال مجدد دستور /start یا تماس با پشتیبانی، دوباره تلاش کنید."
            )
            logger.info(f"User {target_user_id} rejected and notified.")
        except Exception as e:
            logger.error(f"Failed to notify rejected user {target_user_id}: {e}")
    else:
        await query.edit_message_text(f"خطا در رد کاربر `{target_user_id}`.")

# --- Other Placeholder Commands and Handlers (to be expanded in future steps) ---

async def show_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = database.get_user(user_id)
    if user and user.get('is_approved'):
        credit = user.get('credit', 0)
        await update.message.reply_text(f"💳 اعتبار فعلی شما: {credit} واحد")
    else:
        await update.message.reply_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")

async def request_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    user = database.get_user(user_id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")
        return ConversationHandler.END # End the conversation if not approved

    account_types_keyboard = []
    # Fetch prices dynamically
    service_prices = database.get_all_service_prices()

    for acc_type_persian, acc_type_key in config.ACCOUNT_TYPES.items():
        # Using a dummy value for now, will fetch dynamic prices later
        # For simplicity, assume ACCOUNT_TYPES maps to service_type like '1 ماهه' -> 'monthly' if needed
        # Or you might want to link account_type to service_type based on selection in another step
        # For this chunk, let's just list the account types
        account_types_keyboard.append([InlineKeyboardButton(f"{acc_type_persian} ({acc_type_key} اعتبار)", callback_data=f"buy_account_{acc_type_key}")])

    await query.edit_message_text(
        "لطفاً نوع حساب مورد نظر خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(account_types_keyboard)
    )
    return SELECTING_PURCHASE_ACCOUNT_TYPE # New state for purchasing process

async def select_purchase_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    account_type_key = query.data.replace("buy_account_", "")

    user = database.get_user(user_id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("خطا: کاربر نامعتبر است.")
        return ConversationHandler.END

    # Get price from config.ACCOUNT_TYPES for now, will use dynamic prices later
    price = config.ACCOUNT_TYPES.get(account_type_key)
    if price is None:
        await query.edit_message_text("نوع حساب نامعتبر است.")
        return ConversationHandler.END

    if user['credit'] < price:
        await query.edit_message_text(f"اعتبار شما ({user['credit']} واحد) برای خرید این سرویس ({price} واحد) کافی نیست.")
        return ConversationHandler.END

    # Store selected account type
    context.user_data['selected_account_type'] = account_type_key
    context.user_data['selected_price'] = price
    
    # User confirms purchase (implementing here for simplicity, typically another step)
    # This is where credit deduction will happen and service will be delivered by admin action later
    
    await query.edit_message_text(
        f"شما درخواست خرید '{account_type_key}' با هزینه {price} واحد را داده‌اید.\n"
        f"پس از تأیید و ارسال سرویس توسط ادمین، اعتبار شما کسر خواهد شد.\n"
        f"درخواست شما ثبت شد. ادمین به زودی آن را بررسی خواهد کرد."
    )
    # In a real scenario, you'd record this as a pending purchase request for admin approval
    database.add_purchase_request(user_id, account_type_key, 'pending')

    return ConversationHandler.END # End purchase flow for now

async def my_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 این بخش برای نمایش سرویس‌های فعال شماست. (در حال توسعه...)")

async def transfer_credit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    user = database.get_user(user_id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")
        return ConversationHandler.END

    await query.edit_message_text("💰 برای انتقال اعتبار، لطفاً شناسه (ID) کاربری که می‌خواهید به او اعتبار منتقل کنید را وارد کنید:")
    return TRANSFER_USER_ID

async def receive_transfer_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        target_user_id = int(update.message.text.strip())
        if not database.get_user(target_user_id):
            await update.message.reply_text("کاربر با این شناسه یافت نشد. لطفاً شناسه معتبر وارد کنید:")
            return TRANSFER_USER_ID
        if target_user_id == user_id:
            await update.message.reply_text("نمی‌توانید به خودتان اعتبار منتقل کنید. لطفاً شناسه دیگری وارد کنید:")
            return TRANSFER_USER_ID

        context.user_data['target_user_id'] = target_user_id
        await update.message.reply_text(f"میزان اعتباری که می‌خواهید به کاربر `{target_user_id}` منتقل کنید را وارد نمایید:")
        return TRANSFER_AMOUNT
    except ValueError:
        await update.message.reply_text("شناسه کاربری نامعتبر است. لطفاً فقط عدد وارد کنید:")
        return TRANSFER_USER_ID

async def receive_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("مقدار اعتبار باید مثبت باشد. لطفاً عدد معتبر وارد کنید:")
            return TRANSFER_AMOUNT

        sender_user = database.get_user(user_id)
        if sender_user['credit'] < amount:
            await update.message.reply_text(f"اعتبار شما ({sender_user['credit']} واحد) برای انتقال {amount} واحد کافی نیست.")
            return ConversationHandler.END

        target_user_id = context.user_data.get('target_user_id')
        if not target_user_id:
            await update.message.reply_text("خطا در شناسایی کاربر مقصد. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END

        if database.decrease_credit(user_id, amount) and database.increase_credit(target_user_id, amount):
            database.add_credit_transfer(user_id, target_user_id, amount)
            await update.message.reply_text(f"✅ {amount} واحد اعتبار با موفقیت به کاربر `{target_user_id}` منتقل شد.")
            # Notify target user (optional)
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🔔 {amount} واحد اعتبار از طرف کاربر `{user_id}` به شما منتقل شد."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id} about credit transfer: {e}")
        else:
            await update.message.reply_text("خطا در انتقال اعتبار. لطفاً دوباره تلاش کنید.")

        context.user_data.clear() # Clear user_data for this flow
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("مقدار اعتبار نامعتبر است. لطفاً فقط عدد وارد کنید:")
        return TRANSFER_AMOUNT

async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    user = database.get_user(user_id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")
        return ConversationHandler.END
    
    # Placeholder for discount code entry
    await query.edit_message_text("🎁 لطفاً کد تخفیف خود را وارد کنید:")
    return ENTERING_DISCOUNT_CODE

async def enter_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    code = update.message.text.strip()

    discount_value = database.use_discount_code(code)
    if discount_value is not None:
        if database.increase_credit(user_id, discount_value):
            await update.message.reply_text(f"✅ کد تخفیف با موفقیت اعمال شد. {discount_value} واحد اعتبار به حساب شما اضافه شد.")
        else:
            await update.message.reply_text("خطا در اعمال کد تخفیف. لطفاً دوباره تلاش کنید.")
    else:
        await update.message.reply_text("❌ کد تخفیف نامعتبر یا استفاده شده است.")
    return ConversationHandler.END


async def show_help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("راهنمای OpenVPN", callback_data="help_openvpn")],
        [InlineKeyboardButton("راهنمای V2Ray", callback_data="help_v2ray")],
        [InlineKeyboardButton("راهنمای Proxy", callback_data="help_proxy")],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("❓ لطفاً نوع سرویس مورد نظر برای راهنمایی را انتخاب کنید:", reply_markup=reply_markup)


async def send_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    guide_type = query.data.replace("help_", "")
    
    if guide_type == "openvpn":
        # Using config.CONNECTION_GUIDE for OpenVPN images and captions
        images = config.CONNECTION_GUIDE['images']
        captions = config.CONNECTION_GUIDE['captions']
        additional_note = config.CONNECTION_GUIDE['additional_note']
        
        # Send photos with captions
        for i, img_name in enumerate(images):
            try:
                with open(os.path.join(config.IMAGES_DIR, img_name), 'rb') as photo_file:
                    caption_text = captions[i] if i < len(captions) else ""
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=photo_file,
                        caption=caption_text
                    )
            except FileNotFoundError:
                logger.error(f"Image file not found: {img_name}")
                await query.message.reply_text(f"خطا: فایل تصویر {img_name} یافت نشد.")
            except Exception as e:
                logger.error(f"Error sending photo {img_name}: {e}")
                await query.message.reply_text(f"خطا در ارسال تصویر {img_name}.")
                
        await query.message.reply_text(
            f"📥 لینک دانلود OpenVPN Connect:\n"
            f"اندروید: {config.APP_LINKS['android']}\n"
            f"iOS: {config.APP_LINKS['ios']}\n"
            f"ویندوز: {config.APP_LINKS['windows']}\n\n"
            f"{additional_note}"
        )
    elif guide_type == "v2ray":
        # Placeholder for V2Ray guide
        await query.message.reply_text(
            "🚧 راهنمای V2Ray در حال آماده‌سازی است. به زودی اضافه خواهد شد.\n"
            "برای دانلود اپلیکیشن‌های V2Ray:\n"
            "اندروید: [V2RayNG](https://play.google.com/store/apps/details?id=com.v2ray.ang)\n"
            "iOS: [Shadowrocket](https://apps.apple.com/us/app/shadowrocket/id932747118)\n"
            "ویندوز: [V2RayN](https://github.com/2dust/v2rayN/releases)"
        )
    elif guide_type == "proxy":
        # Placeholder for Proxy guide
        await query.message.reply_text(
            "🚧 راهنمای Proxy تلگرام در حال آماده‌سازی است. به زودی اضافه خواهد شد.\n"
            "برای اتصال به پروکسی تلگرام، کافیست روی لینک پروکسی کلیک کنید."
        )
    
    # After sending guide, optionally return to main menu or a guide menu
    await query.message.reply_text("بازگشت به منوی اصلی:", reply_markup=get_main_menu_keyboard())

async def send_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = database.get_user(user_id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")
        return ConversationHandler.END

    await query.edit_message_text("✉️ پیام خود را برای پشتیبانی وارد کنید:")
    return ENTERING_SUPPORT_MESSAGE

async def receive_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    message_text = update.message.text.strip()

    if not message_text:
        await update.message.reply_text("پیام نمی‌تواند خالی باشد. لطفاً پیام خود را وارد کنید:")
        return ENTERING_SUPPORT_MESSAGE

    if database.add_support_message(user_id, message_text):
        await update.message.reply_text("✅ پیام شما با موفقیت برای پشتیبانی ارسال شد. به زودی پاسخ داده خواهد شد.")
        # Notify admin about new support message
        user = database.get_user(user_id)
        username_str = f"@{user['username']}" if user['username'] else f"ID: {user['id']}"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"پیام پشتیبانی جدید از {username_str}:\n\n{message_text}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ خطا در ارسال پیام پشتیبانی. لطفاً دوباره تلاش کنید.")
    return ConversationHandler.END

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query if update.callback_query else update.message
    await (query.answer() if update.callback_query else logger.info("About command invoked"))
    
    text = (
        "ℹ️ **درباره ربات VPN ما**\n\n"
        "این ربات برای ارائه دسترسی آسان و امن به اینترنت از طریق سرویس‌های VPN طراحی شده است.\n"
        "ما تلاش می‌کنیم بهترین تجربه را برای کاربران خود فراهم کنیم.\n\n"
        "**قابلیت‌های اصلی:**\n"
        "  •  خرید و مدیریت سرویس‌های VPN (OpenVPN, V2Ray, Proxy)\n"
        "  •  مدیریت اعتبار حساب\n"
        "  •  پشتیبانی آنلاین\n"
        "  •  کدهای تخفیف و پیشنهادات ویژه\n\n"
        "با ما در ارتباط باشید و از اینترنت آزاد لذت ببرید!"
    )
    if update.callback_query:
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_menu_keyboard())


# --- Admin Panel Handlers (initial setup) ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("شما اجازه دسترسی به پنل ادمین را ندارید.")
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("شما اجازه دسترسی به پنل ادمین را ندارید.")
        return ConversationHandler.END

    if update.message:
        await update.message.reply_text("به پنل ادمین خوش آمدید.", reply_markup=get_admin_panel_keyboard())
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("به پنل ادمین خوش آمدید.", reply_markup=get_admin_panel_keyboard())
    return ADMIN_MAIN_MENU

async def admin_manage_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("لیست کاربران", callback_data="admin_list_all_users")],
        [InlineKeyboardButton("کاربران در انتظار تأیید", callback_data="admin_list_pending_users")],
        [InlineKeyboardButton("افزایش/کاهش اعتبار کاربر", callback_data="admin_select_user_for_credit")], # New action
        [InlineKeyboardButton("بازگشت به پنل ادمین", callback_data="admin_panel_back")]
    ]
    await query.edit_message_text("مدیریت کاربران:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_MANAGE_USERS_MENU

async def admin_list_pending_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    pending_users = database.get_pending_users()
    if not pending_users:
        await query.edit_message_text("هیچ کاربر در انتظار تأیید وجود ندارد.")
        return ADMIN_MANAGE_USERS_MENU

    user_list_text = "کاربران در انتظار تأیید:\n"
    keyboard = []
    for user in pending_users:
        user_list_text += (
            f"ID: `{user['id']}` | "
            f"@{user['username']} | "
            f"نام: {user.get('full_name', 'نامشخص')} | "
            f"شماره: {user.get('phone_number', 'نامشخص')} | "
            f"سیستم‌عامل: {user.get('requested_os', 'نامشخص')}\n"
        )
        keyboard.append([InlineKeyboardButton(f"بررسی کاربر {user['id']}", callback_data=f"admin_review_user_{user['id']}")])
    
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_manage_users_menu")])

    await query.edit_message_text(
        user_list_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ADMIN_MANAGE_USERS_MENU # Stay in user management menu

async def admin_review_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    target_user_id = int(query.data.replace("admin_review_user_", ""))
    user = database.get_user(target_user_id)
    
    if not user:
        await query.edit_message_text("کاربر یافت نشد.")
        return ADMIN_MANAGE_USERS_MENU

    message_text = (
        f"درخواست تأیید کاربر:\n"
        f"ID: `{user['id']}`\n"
        f"نام کاربری تلگرام: @{user['username']}\n" if user['username'] else f"نام کاربری تلگرام: ندارد\n"
        f"نام کامل: {user.get('full_name', 'نامشخص')}\n"
        f"شماره تماس: {user.get('phone_number', 'نامشخص')}\n"
        f"سیستم‌عامل درخواستی: {user.get('requested_os', 'نامشخص')}\n"
        f"تاریخ ثبت‌نام: {user.get('registration_date', 'نامشخص')}\n"
        f"وضعیت فعلی: {'تأیید شده' if user['is_approved'] else 'در انتظار تأیید'}"
    )

    keyboard = [[
        InlineKeyboardButton("✅ تأیید کاربر", callback_data=f"admin_approve_user_{user['id']}"),
        InlineKeyboardButton("❌ رد کاربر", callback_data=f"admin_reject_user_{user['id']}")
    ], [
        InlineKeyboardButton("بازگشت", callback_data="admin_list_pending_users")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ADMIN_USER_DETAIL_VIEW # A new state to keep context for user review

async def admin_list_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    all_users = database.get_all_users()
    if not all_users:
        await query.edit_message_text("هیچ کاربری در دیتابیس وجود ندارد.")
        return ADMIN_MANAGE_USERS_MENU

    user_list_text = "لیست همه کاربران:\n"
    keyboard = []
    for user in all_users:
        user_list_text += (
            f"ID: `{user['id']}` | "
            f"@{user['username']} | "
            f"اعتبار: {user['credit']} | "
            f"وضعیت: {'تایید' if user['is_approved'] else 'در انتظار'}\n"
        )
        keyboard.append([InlineKeyboardButton(f"مدیریت کاربر {user['id']}", callback_data=f"admin_manage_specific_user_{user['id']}")])
    
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_manage_users_menu")])

    await query.edit_message_text(
        user_list_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return ADMIN_MANAGE_USERS_MENU

async def admin_manage_specific_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    target_user_id = int(query.data.replace("admin_manage_specific_user_", ""))
    user = database.get_user(target_user_id)

    if not user:
        await query.edit_message_text("کاربر یافت نشد.")
        return ADMIN_MANAGE_USERS_MENU

    context.user_data['target_admin_action_user_id'] = target_user_id # Store for later actions

    message_text = (
        f"مدیریت کاربر `{user['id']}`:\n"
        f"نام کاربری: @{user['username']}\n" if user['username'] else "نام کاربری: ندارد\n"
        f"نام کامل: {user.get('full_name', 'نامشخص')}\n"
        f"شماره تماس: {user.get('phone_number', 'نامشخص')}\n"
        f"اعتبار: {user['credit']}\n"
        f"وضعیت: {'تأیید شده' if user['is_approved'] else 'در انتظار تأیید'}\n"
    )

    keyboard = [
        [InlineKeyboardButton("➕ افزایش اعتبار", callback_data=f"admin_add_credit_to_{target_user_id}")],
        [InlineKeyboardButton("➖ کاهش اعتبار", callback_data=f"admin_decrease_credit_from_{target_user_id}")],
        [InlineKeyboardButton("ارسال سرویس", callback_data=f"admin_send_service_to_{target_user_id}")], # New action
        [InlineKeyboardButton("بازگشت به لیست کاربران", callback_data="admin_list_all_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    return ADMIN_USER_DETAIL_VIEW # Stay in user detail view for actions


async def admin_add_credit_to_user_init(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    target_user_id = int(query.data.replace("admin_add_credit_to_", ""))
    context.user_data['target_credit_user_id'] = target_user_id # Store for next step
    
    await query.edit_message_text(f"مقدار اعتباری که می‌خواهید به کاربر `{target_user_id}` اضافه کنید را وارد کنید:")
    return ADMIN_USER_ADD_CREDIT_AMOUNT

async def admin_decrease_credit_from_user_init(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    target_user_id = int(query.data.replace("admin_decrease_credit_from_", ""))
    context.user_data['target_credit_user_id'] = target_user_id # Store for next step
    context.user_data['credit_action'] = 'decrease' # Store action type
    
    await query.edit_message_text(f"مقدار اعتباری که می‌خواهید از کاربر `{target_user_id}` کسر کنید را وارد کنید:")
    return ADMIN_USER_ADD_CREDIT_AMOUNT


async def admin_receive_credit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    admin_id = update.effective_user.id
    target_user_id = context.user_data.get('target_credit_user_id')
    credit_action = context.user_data.get('credit_action', 'increase') # Default to increase

    if not target_user_id:
        await update.message.reply_text("خطا: شناسه کاربر مقصد نامشخص است. لطفاً از ابتدا شروع کنید.")
        context.user_data.clear()
        return ADMIN_MAIN_MENU

    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("مقدار اعتبار باید یک عدد مثبت باشد. لطفا دوباره وارد کنید:")
            return ADMIN_USER_ADD_CREDIT_AMOUNT

        success = False
        if credit_action == 'increase':
            success = database.increase_credit(target_user_id, amount)
            action_text = "افزایش"
        else: # decrease
            success = database.decrease_credit(target_user_id, amount)
            action_text = "کاهش"

        if success:
            await update.message.reply_text(f"✅ {amount} واحد اعتبار برای کاربر `{target_user_id}` با موفقیت {action_text} یافت.")
            # Optionally notify the user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🔔 {amount} واحد اعتبار به حساب شما {action_text} یافت."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_user_id} about credit {action_text}: {e}")
        else:
            await update.message.reply_text(f"❌ خطا در {action_text} اعتبار برای کاربر `{target_user_id}`. (اعتبار کافی نبود یا خطای دیتابیس)")

    except ValueError:
        await update.message.reply_text("مقدار اعتبار نامعتبر است. لطفاً فقط عدد وارد کنید:")
        return ADMIN_USER_ADD_CREDIT_AMOUNT
    
    context.user_data.clear() # Clear specific user data for this action
    return ConversationHandler.END # End the conversation for this specific credit action

async def admin_manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("تنظیم محتوای سرویس", callback_data="admin_set_service_content_entry")],
        [InlineKeyboardButton("بازگشت به پنل ادمین", callback_data="admin_panel_back")]
    ]
    await query.edit_message_text("مدیریت سرویس‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_MANAGE_SERVICES_MENU

async def admin_set_service_content_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for text, data in config.SERVICE_TYPES.items():
        keyboard.append([InlineKeyboardButton(text, callback_data=f"set_service_content_{data}")])
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_manage_services_menu")])

    await query.edit_message_text("لطفاً نوع سرویسی که می‌خواهید محتوایش را تنظیم کنید، انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_SET_SERVICE # Reusing this state for selection

async def admin_set_service_content_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("set_service_content_", "")
    context.user_data['service_type_to_set'] = service_type
    
    keyboard = [
        [InlineKeyboardButton("فایل (مثلاً کانفیگ OpenVPN)", callback_data="service_content_type_file")],
        [InlineKeyboardButton("متن (مثلاً لینک V2Ray یا پروکسی)", callback_data="service_content_type_text")]
    ]
    await query.edit_message_text(f"محتوای سرویس '{service_type}' از چه نوعی است؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_SERVICE_FILE_OR_TEXT

async def admin_receive_service_content_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    content_type = query.data.replace("service_content_type_", "")
    service_type = context.user_data.get('service_type_to_set')
    
    if not service_type:
        await query.edit_message_text("خطا: نوع سرویس نامشخص است. لطفاً دوباره تلاش کنید.")
        return ADMIN_MANAGE_SERVICES_MENU

    context.user_data['service_content_is_file'] = (content_type == 'file')
    
    if content_type == 'file':
        await query.edit_message_text(f"لطفاً فایل (مثلاً کانفیگ) سرویس '{service_type}' را ارسال کنید.")
    else: # text
        await query.edit_message_text(f"لطفاً محتوای متنی (مثلاً لینک) سرویس '{service_type}' را وارد کنید.")
    
    return ADMIN_SET_SERVICE_CONTENT


async def admin_receive_service_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_type = context.user_data.get('service_type_to_set')
    is_file = context.user_data.get('service_content_is_file')
    
    if not service_type:
        await update.message.reply_text("خطا: نوع سرویس نامشخص است. لطفاً از ابتدا شروع کنید.")
        context.user_data.clear()
        return ADMIN_MAIN_MENU

    content = None
    file_name = None

    if is_file:
        if update.message.document:
            document = update.message.document
            file_name = document.file_name
            file_id = document.file_id
            
            # Download the file
            new_file = await context.bot.get_file(file_id)
            file_path = os.path.join(config.CONFIGS_DIR, file_name)
            await new_file.download_to_drive(file_path)
            content = file_path # Store path to file
            
            # Optional: Read content into DB directly if small enough, or just store path
            # For now, store path and is_file flag
        else:
            await update.message.reply_text("لطفاً یک فایل ارسال کنید.")
            return ADMIN_SET_SERVICE_CONTENT # Stay in this state
    else: # text content
        content = update.message.text.strip()
        if not content:
            await update.message.reply_text("محتوای متنی نمی‌تواند خالی باشد. لطفاً محتوا را وارد کنید.")
            return ADMIN_SET_SERVICE_CONTENT # Stay in this state
    
    if database.set_service(service_type, content, is_file, file_name):
        await update.message.reply_text(f"✅ محتوای سرویس '{service_type}' با موفقیت ذخیره شد.")
    else:
        await update.message.reply_text(f"❌ خطا در ذخیره محتوای سرویس '{service_type}'.")

    context.user_data.clear() # Clear data for this flow
    return ConversationHandler.END # End this specific admin conversation

async def admin_set_service_prices_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = []
    for text, data in config.SERVICE_TYPES.items():
        keyboard.append([InlineKeyboardButton(text, callback_data=f"set_price_for_{data}")])
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")])

    await query.edit_message_text(
        "💲 قیمت کدام سرویس را می‌خواهید تنظیم کنید؟\n"
        "قیمت‌های فعلی:\n" + 
        "\n".join([f"- {s_type}: {price}" for s_type, price in database.get_all_service_prices().items()]),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ADMIN_SET_SERVICE_PRICE_TYPE

async def admin_set_service_price_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("set_price_for_", "")
    context.user_data['service_price_type'] = service_type
    
    await query.edit_message_text(f"لطفاً قیمت جدید (عدد) برای سرویس '{service_type}' را وارد کنید:")
    return ADMIN_SET_SERVICE_PRICE_VALUE

async def admin_receive_service_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_type = context.user_data.get('service_price_type')
    if not service_type:
        await update.message.reply_text("خطا: نوع سرویس برای تنظیم قیمت نامشخص است. لطفاً از ابتدا شروع کنید.")
        context.user_data.clear()
        return ADMIN_MAIN_MENU

    try:
        price = int(update.message.text.strip())
        if price < 0:
            await update.message.reply_text("قیمت نمی‌تواند منفی باشد. لطفا عدد معتبر وارد کنید:")
            return ADMIN_SET_SERVICE_PRICE_VALUE
        
        if database.set_service_price(service_type, price):
            await update.message.reply_text(f"✅ قیمت سرویس '{service_type}' با موفقیت به {price} تنظیم شد.")
        else:
            await update.message.reply_text(f"❌ خطا در تنظیم قیمت سرویس '{service_type}'.")
            
    except ValueError:
        await update.message.reply_text("مقدار قیمت نامعتبر است. لطفاً فقط عدد وارد کنید:")
        return ADMIN_SET_SERVICE_PRICE_VALUE
    
    context.user_data.clear()
    return ConversationHandler.END # End this specific admin conversation

async def admin_manage_discounts_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("ایجاد کد تخفیف جدید", callback_data="admin_add_discount_code")],
        [InlineKeyboardButton("حذف کد تخفیف", callback_data="admin_delete_discount_code")],
        [InlineKeyboardButton("لیست کدهای تخفیف", callback_data="admin_list_discount_codes")],
        [InlineKeyboardButton("بازگشت به پنل ادمین", callback_data="admin_panel_back")]
    ]
    await query.edit_message_text("مدیریت کدهای تخفیف:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_DISCOUNT_CODES

async def admin_add_discount_code_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً کد تخفیف و مقدار آن را وارد کنید (مثال: MYCODE 100):")
    return ADMIN_ADD_DISCOUNT_VALUE

async def admin_receive_new_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("فرمت نامعتبر است. مثال: MYCODE 100")
            return ADMIN_ADD_DISCOUNT_VALUE
        
        code = parts[0]
        value = int(parts[1])
        if value <= 0:
            await update.message.reply_text("مقدار کد تخفیف باید مثبت باشد. لطفا عدد معتبر وارد کنید.")
            return ADMIN_ADD_DISCOUNT_VALUE

        if database.add_discount_code(code, value):
            await update.message.reply_text(f"✅ کد تخفیف '{code}' با مقدار {value} با موفقیت اضافه شد.")
        else:
            await update.message.reply_text("❌ کد تخفیف از قبل وجود دارد یا خطایی رخ داد.")
    except ValueError:
        await update.message.reply_text("مقدار کد تخفیف نامعتبر است. لطفاً عدد وارد کنید.")
        return ADMIN_ADD_DISCOUNT_VALUE
    
    return ConversationHandler.END

async def admin_delete_discount_code_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    codes = database.get_all_discount_codes()
    if not codes:
        await query.edit_message_text("هیچ کد تخفیفی برای حذف وجود ندارد.")
        return ADMIN_DISCOUNT_CODES
    
    code_list_text = "کدهای تخفیف موجود:\n" + "\n".join([f"- {c['code']} (مقدار: {c['value']}, استفاده: {c['usage_count']})" for c in codes])
    await query.edit_message_text(f"{code_list_text}\n\nلطفاً کدی که می‌خواهید حذف کنید را وارد کنید:")
    return ADMIN_DELETE_DISCOUNT

async def admin_confirm_delete_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip()
    if database.delete_discount_code(code):
        await update.message.reply_text(f"✅ کد تخفیف '{code}' با موفقیت حذف شد.")
    else:
        await update.message.reply_text("❌ کد تخفیف یافت نشد یا خطایی رخ داد.")
    return ConversationHandler.END

async def admin_list_discount_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    codes = database.get_all_discount_codes()
    if not codes:
        await query.edit_message_text("هیچ کد تخفیفی در حال حاضر وجود ندارد.")
        return
    
    code_list_text = "لیست کدهای تخفیف:\n\n"
    for code in codes:
        code_list_text += (
            f"کد: `{code['code']}`\n"
            f"مقدار: {code['value']} واحد\n"
            f"تعداد استفاده: {code['usage_count']}\n"
            f"تاریخ ایجاد: {code['created_date']}\n"
            f"-----------\n"
        )
    await query.edit_message_text(code_list_text, parse_mode='Markdown')

async def admin_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    stats = database.get_bot_statistics()
    stats_text = (
        f"📊 آمار ربات:\n\n"
        f"👥 کل کاربران: {stats.get('total_users', 0)}\n"
        f"✅ کاربران تأیید شده: {stats.get('approved_users', 0)}\n"
        f"⏳ کاربران در انتظار تأیید: {stats.get('pending_users', 0)}\n"
        f"💰 کل اعتبار توزیع شده: {stats.get('total_credit', 0)}\n"
        f"🏷️ کل کدهای تخفیف: {stats.get('total_discount_codes', 0)}\n"
        f"✉️ کل پیام‌های پشتیبانی: {stats.get('total_support_messages', 0)}\n"
        f"💲 قیمت سرویس‌ها:\n"
    )
    for s_type, price in database.get_all_service_prices().items():
        stats_text += f"- {s_type}: {price}\n"

    await query.edit_message_text(stats_text, parse_mode='Markdown')


async def admin_broadcast_message_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً پیام همگانی خود را برای ارسال به همه کاربران وارد کنید:")
    return ADMIN_BROADCAST_MESSAGE

async def admin_receive_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text.strip()
    if not message_text:
        await update.message.reply_text("پیام نمی‌تواند خالی باشد. لطفا دوباره وارد کنید:")
        return ADMIN_BROADCAST_MESSAGE
    
    context.user_data['broadcast_message'] = message_text
    
    keyboard = [[
        InlineKeyboardButton("✅ تأیید و ارسال", callback_data="confirm_broadcast"),
        InlineKeyboardButton("❌ لغو", callback_data="cancel_broadcast")
    ]]
    await update.message.reply_text(f"پیام شما:\n---\n{message_text}\n---\nآیا از ارسال آن به همه کاربران مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_BROADCAST_CONFIRM

async def admin_confirm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    broadcast_message = context.user_data.get('broadcast_message')
    if query.data == "cancel_broadcast":
        await query.edit_message_text("ارسال پیام همگانی لغو شد.")
        context.user_data.clear()
        return ConversationHandler.END

    if not broadcast_message:
        await query.edit_message_text("خطا: پیام همگانی یافت نشد. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    users = database.get_all_users()
    sent_count = 0
    failed_count = 0
    
    await query.edit_message_text("در حال ارسال پیام همگانی...")

    for user in users:
        try:
            await context.bot.send_message(chat_id=user['id'], text=broadcast_message)
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user['id']}: {e}")
            failed_count += 1
            
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"✅ ارسال پیام همگانی تکمیل شد.\nارسال موفق: {sent_count}\nناموفق: {failed_count}"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def admin_manage_purchase_requests_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("درخواست‌های در انتظار", callback_data="admin_view_pending_purchase_requests")],
        [InlineKeyboardButton("درخواست‌های تأیید شده", callback_data="admin_view_approved_purchase_requests")],
        [InlineKeyboardButton("بازگشت به پنل ادمین", callback_data="admin_panel_back")]
    ]
    await query.edit_message_text("مدیریت درخواست‌های خرید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ADMIN_REQUESTS_MENU

async def admin_view_pending_purchase_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    pending_requests = database.get_purchase_requests_by_status('pending')

    if not pending_requests:
        await query.edit_message_text("هیچ درخواست خرید در انتظار تأییدی وجود ندارد.")
        return ADMIN_REQUESTS_MENU

    message_text = "درخواست‌های خرید در انتظار تأیید:\n\n"
    keyboard = []
    for req in pending_requests:
        user = database.get_user(req['user_id'])
        username = user['username'] if user and user['username'] else f"ID: {req['user_id']}"
        message_text += (
            f"**ID درخواست:** `{req['id']}`\n"
            f"**کاربر:** {username} (ID: `{req['user_id']}`)\n"
            f"**نوع حساب:** {req['account_type']}\n"
            f"**تاریخ:** {req['request_date']}\n"
            f"---------\n"
        )
        keyboard.append([InlineKeyboardButton(f"بررسی درخواست {req['id']}", callback_data=f"admin_process_purchase_request_{req['id']}")])
    
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_manage_purchase_requests_entry")])

    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_VIEW_PENDING_REQUESTS # Stay in pending requests view

async def admin_view_approved_purchase_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    approved_requests = database.get_purchase_requests_by_status('approved')

    if not approved_requests:
        await query.edit_message_text("هیچ درخواست خرید تأیید شده‌ای وجود ندارد.")
        return ADMIN_REQUESTS_MENU

    message_text = "درخواست‌های خرید تأیید شده:\n\n"
    for req in approved_requests:
        user = database.get_user(req['user_id'])
        username = user['username'] if user and user['username'] else f"ID: {req['user_id']}"
        message_text += (
            f"**ID درخواست:** `{req['id']}`\n"
            f"**کاربر:** {username} (ID: `{req['user_id']}`)\n"
            f"**نوع حساب:** {req['account_type']}\n"
            f"**تاریخ:** {req['request_date']}\n"
            f"**وضعیت:** {req['status']}\n" # Should be 'approved'
            f"---------\n"
        )
    
    keyboard = [[InlineKeyboardButton("بازگشت", callback_data="admin_manage_purchase_requests_entry")]]
    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_VIEW_APPROVED_REQUESTS

async def admin_process_purchase_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    request_id = int(query.data.replace("admin_process_purchase_request_", ""))
    purchase_request = database.get_purchase_request_by_id(request_id)

    if not purchase_request:
        await query.edit_message_text("درخواست خرید یافت نشد.")
        return ADMIN_VIEW_PENDING_REQUESTS

    user = database.get_user(purchase_request['user_id'])
    if not user:
        await query.edit_message_text("کاربر مربوط به این درخواست یافت نشد.")
        return ADMIN_VIEW_PENDING_REQUESTS
    
    # Calculate price based on account_type and dynamic service prices (if applicable)
    # For now, let's assume price from config.ACCOUNT_TYPES or a lookup if account_type maps to a service_type
    # A more robust system would map '1 ماهه' to an OpenVPN price or V2Ray price depending on what service is being bought
    # For simplicity, let's use a fixed price for "1 ماهه" etc. based on config.ACCOUNT_TYPES for now,
    # or ensure account_type maps directly to a service_type for price lookup.
    
    # Let's assume ACCOUNT_TYPES keys are what we use for direct price lookup or simple fixed value
    # If "1 ماهه" maps to OpenVPN, we'd use get_service_price('openvpn')
    # For now, we take from config.ACCOUNT_TYPES directly
    price = config.ACCOUNT_TYPES.get(purchase_request['account_type']) # This needs to be refined based on actual service
    if price is None:
        await query.edit_message_text(f"خطا: قیمت برای نوع حساب '{purchase_request['account_type']}' یافت نشد.")
        return ADMIN_VIEW_PENDING_REQUESTS

    context.user_data['current_purchase_request_id'] = request_id
    context.user_data['purchase_user_id'] = user['id']
    context.user_data['purchase_account_type'] = purchase_request['account_type']
    context.user_data['purchase_price'] = price


    message_text = (
        f"**بررسی درخواست خرید:**\n"
        f"**ID درخواست:** `{purchase_request['id']}`\n"
        f"**کاربر:** @{user['username']} (ID: `{user['id']}`)\n"
        f"**نوع حساب:** {purchase_request['account_type']}\n"
        f"**اعتبار فعلی کاربر:** {user['credit']}\n"
        f"**هزینه سرویس:** {price} واحد\n"
        f"**وضعیت:** {purchase_request['status']}\n"
        f"**تاریخ درخواست:** {purchase_request['request_date']}\n"
    )

    keyboard = []
    # Only show 'Approve' if user has enough credit, or admin overrides
    if user['credit'] >= price:
        keyboard.append([InlineKeyboardButton("✅ تأیید و کسر اعتبار", callback_data="admin_confirm_purchase_deduct")])
    else:
        message_text += "\n⚠️ **کاربر اعتبار کافی ندارد!**"
        keyboard.append([InlineKeyboardButton("✅ تأیید و ارسال (بدون کسر اعتبار)", callback_data="admin_confirm_purchase_no_deduct")])
    
    keyboard.append([InlineKeyboardButton("❌ رد درخواست", callback_data="admin_reject_purchase_request")])
    keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_view_pending_purchase_requests")])

    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ADMIN_PROCESS_REQUEST

async def admin_confirm_purchase_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    request_id = context.user_data.get('current_purchase_request_id')
    purchase_user_id = context.user_data.get('purchase_user_id')
    purchase_account_type = context.user_data.get('purchase_account_type')
    purchase_price = context.user_data.get('purchase_price')

    if not all([request_id, purchase_user_id, purchase_account_type, purchase_price]):
        await query.edit_message_text("خطا: اطلاعات درخواست خرید ناقص است. لطفاً دوباره تلاش کنید.")
        context.user_data.clear()
        return ADMIN_MAIN_MENU

    user = database.get_user(purchase_user_id)
    if not user:
        await query.edit_message_text("خطا: کاربر مربوط به این درخواست یافت نشد.")
        context.user_data.clear()
        return ADMIN_MAIN_MENU

    action = query.data

    if action == "admin_confirm_purchase_deduct":
        if database.decrease_credit(purchase_user_id, purchase_price) and \
           database.update_purchase_request_status(request_id, 'approved'):
            
            # Here, determine which service content to send based on purchase_account_type
            # For simplicity, let's assume '1 ماهه', '3 ماهه' etc. are OpenVPN, 'ویژه' is V2Ray, 'اکسس پوینت' is Proxy
            # This mapping needs to be clearly defined or handled in a more flexible way
            
            # Example mapping (you need to define this logically based on your business rules)
            service_type_to_send = None
            if "ماه" in purchase_account_type: # e.g., "1 ماهه", "3 ماهه"
                service_type_to_send = "openvpn" # Assuming OpenVPN is default for subscription types
            elif "ویژه" in purchase_account_type:
                service_type_to_send = "v2ray"
            elif "اکسس پوینت" in purchase_account_type:
                service_type_to_send = "proxy"
            
            if service_type_to_send:
                service = database.get_service(service_type_to_send)
                if service:
                    if service['is_file']:
                        try:
                            with open(service['content'], 'rb') as service_file:
                                await context.bot.send_document(
                                    chat_id=purchase_user_id,
                                    document=service_file,
                                    caption=f"✅ سرویس {service_type_to_send} شما آماده است! اعتبار شما به میزان {purchase_price} واحد کسر شد."
                                )
                            await query.edit_message_text(f"✅ درخواست `{request_id}` تأیید و سرویس ({service_type_to_send}) ارسال شد. اعتبار {purchase_price} واحد از کاربر `{purchase_user_id}` کسر شد.")
                        except FileNotFoundError:
                            await query.edit_message_text(f"خطا: فایل سرویس {service_type_to_send} یافت نشد.")
                            logger.error(f"Service file not found for {service_type_to_send}: {service['content']}")
                        except Exception as e:
                            await query.edit_message_text(f"خطا در ارسال فایل سرویس {service_type_to_send}: {e}")
                            logger.error(f"Error sending service file for {service_type_to_send}: {e}")
                    else: # Text content
                        await context.bot.send_message(
                            chat_id=purchase_user_id,
                            text=f"✅ سرویس {service_type_to_send} شما آماده است!\n\nمحتوا:\n`{service['content']}`\n\nاعتبار شما به میزان {purchase_price} واحد کسر شد.",
                            parse_mode='Markdown'
                        )
                        await query.edit_message_text(f"✅ درخواست `{request_id}` تأیید و سرویس ({service_type_to_send}) ارسال شد. اعتبار {purchase_price} واحد از کاربر `{purchase_user_id}` کسر شد.")
                else:
                    await query.edit_message_text(f"خطا: محتوای سرویس {service_type_to_send} در دیتابیس یافت نشد.")
            else:
                await query.edit_message_text(f"خطا: نوع سرویس قابل ارسال برای '{purchase_account_type}' تعریف نشده است.")
        else:
            await query.edit_message_text(f"❌ خطا در تأیید و کسر اعتبار برای درخواست `{request_id}`.")
    
    elif action == "admin_confirm_purchase_no_deduct":
        if database.update_purchase_request_status(request_id, 'approved'):
            service_type_to_send = None
            if "ماه" in purchase_account_type:
                service_type_to_send = "openvpn"
            elif "ویژه" in purchase_account_type:
                service_type_to_send = "v2ray"
            elif "اکسس پوینت" in purchase_account_type:
                service_type_to_send = "proxy"
            
            if service_type_to_send:
                service = database.get_service(service_type_to_send)
                if service:
                    if service['is_file']:
                        try:
                            with open(service['content'], 'rb') as service_file:
                                await context.bot.send_document(
                                    chat_id=purchase_user_id,
                                    document=service_file,
                                    caption=f"✅ سرویس {service_type_to_send} شما آماده است! (اعتبار کسر نشد)"
                                )
                            await query.edit_message_text(f"✅ درخواست `{request_id}` تأیید و سرویس ({service_type_to_send}) ارسال شد. (اعتبار کسر نشد)")
                        except FileNotFoundError:
                            await query.edit_message_text(f"خطا: فایل سرویس {service_type_to_send} یافت نشد.")
                        except Exception as e:
                            await query.edit_message_text(f"خطا در ارسال فایل سرویس {service_type_to_send}: {e}")
                    else:
                        await context.bot.send_message(
                            chat_id=purchase_user_id,
                            text=f"✅ سرویس {service_type_to_send} شما آماده است!\n\nمحتوا:\n`{service['content']}`\n\n(اعتبار کسر نشد)",
                            parse_mode='Markdown'
                        )
                        await query.edit_message_text(f"✅ درخواست `{request_id}` تأیید و سرویس ({service_type_to_send}) ارسال شد. (اعتبار کسر نشد)")
                else:
                    await query.edit_message_text(f"خطا: محتوای سرویس {service_type_to_send} در دیتابیس یافت نشد.")
            else:
                await query.edit_message_text(f"خطا: نوع سرویس قابل ارسال برای '{purchase_account_type}' تعریف نشده است.")
        else:
            await query.edit_message_text(f"❌ خطا در تأیید درخواست `{request_id}` (بدون کسر اعتبار).")

    elif action == "admin_reject_purchase_request":
        if database.update_purchase_request_status(request_id, 'rejected'):
            await query.edit_message_text(f"❌ درخواست `{request_id}` رد شد.")
            try:
                await context.bot.send_message(
                    chat_id=purchase_user_id,
                    text=f"متاسفانه درخواست خرید سرویس شما ({purchase_account_type}) رد شد. لطفاً در صورت نیاز با پشتیبانی تماس بگیرید."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {purchase_user_id} about rejected purchase: {e}")
        else:
            await query.edit_message_text(f"❌ خطا در رد درخواست `{request_id}`.")
    
    context.user_data.clear()
    return ConversationHandler.END


# --- General Callbacks (for returning to menus) ---

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = database.get_user(query.from_user.id)
    if not user or not user.get('is_approved'):
        await query.edit_message_text("لطفا ابتدا مراحل ثبت نام و تایید را تکمیل کنید.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"سلام {query.from_user.first_name} عزیز! به ربات VPN ما خوش آمدید.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END # End the current conversation and return to main menu context

async def admin_panel_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("به پنل ادمین خوش آمدید.", reply_markup=get_admin_panel_keyboard())
    return ADMIN_MAIN_MENU

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    if update.message:
        await update.message.reply_text(
            "عملیات لغو شد.", reply_markup=ReplyKeyboardRemove()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "عملیات لغو شد."
        )
    context.user_data.clear() # Clear any user-specific data from the current conversation
    return ConversationHandler.END

# --- Main function ---

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # User Registration and Main Menu Conversation Handler
    user_flow_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            REQUESTING_CONTACT: [MessageHandler(filters.CONTACT & ~filters.COMMAND, receive_contact)],
            REQUESTING_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_full_name)],
            SELECTING_OS: [CallbackQueryHandler(receive_os_selection, pattern="^os_select_")],
            
            # User Main Menu Callbacks (handle them outside or chain them based on your flow)
            # For now, these just call the relevant functions
            SELECTING_PURCHASE_ACCOUNT_TYPE: [CallbackQueryHandler(select_purchase_account_type, pattern="^buy_account_")],
            ENTERING_DISCOUNT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_discount_code)],
            TRANSFER_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_transfer_user_id)],
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_transfer_amount)],
            ENTERING_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_support_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True # Allow users to restart the process if they get stuck
    )
    application.add_handler(user_flow_conv_handler)
    
    # Global CallbackQueryHandler for main menu items when not in a specific conversation
    application.add_handler(CallbackQueryHandler(show_credit_command, pattern="^show_credit$"))
    application.add_handler(CallbackQueryHandler(request_service, pattern="^request_service$"))
    application.add_handler(CallbackQueryHandler(my_services, pattern="^my_services$"))
    application.add_handler(CallbackQueryHandler(transfer_credit, pattern="^transfer_credit$"))
    application.add_handler(CallbackQueryHandler(apply_discount, pattern="^apply_discount$"))
    application.add_handler(CallbackQueryHandler(show_help_menu, pattern="^show_help_menu$"))
    application.add_handler(CallbackQueryHandler(send_support_message, pattern="^send_support_message$"))
    application.add_handler(CallbackQueryHandler(about_command, pattern="^about_us$"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")) # New callback for returning to main menu

    # Help Menu Callbacks
    application.add_handler(CallbackQueryHandler(send_guide, pattern="^help_"))

    # Admin Panel Handlers
    application.add_handler(CommandHandler("admin", admin_panel)) # Entry point for admin panel
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel_back$")) # To return to admin panel

    # Admin User Management
    application.add_handler(CallbackQueryHandler(admin_manage_users_menu, pattern="^admin_manage_users_menu$"))
    application.add_handler(CallbackQueryHandler(admin_list_pending_users, pattern="^admin_list_pending_users$"))
    application.add_handler(CallbackQueryHandler(admin_review_user, pattern="^admin_review_user_")) # Review specific pending user
    application.add_handler(CallbackQueryHandler(handle_admin_approve_user, pattern="^admin_approve_user_")) # Approve
    application.add_handler(CallbackQueryHandler(handle_admin_reject_user, pattern="^admin_reject_user_")) # Reject
    application.add_handler(CallbackQueryHandler(admin_list_all_users, pattern="^admin_list_all_users$"))
    application.add_handler(CallbackQueryHandler(admin_manage_specific_user, pattern="^admin_manage_specific_user_"))
    
    # Admin Credit Management (inside user management flow)
    application.add_handler(CallbackQueryHandler(admin_add_credit_to_user_init, pattern="^admin_add_credit_to_"))
    application.add_handler(CallbackQueryHandler(admin_decrease_credit_from_user_init, pattern="^admin_decrease_credit_from_"))
    
    # Admin Service Management
    application.add_handler(CallbackQueryHandler(admin_manage_services_menu, pattern="^admin_manage_services_menu$"))
    application.add_handler(CallbackQueryHandler(admin_set_service_content_entry, pattern="^admin_set_service_content_entry$"))
    application.add_handler(CallbackQueryHandler(admin_set_service_content_type, pattern="^set_service_content_"))
    application.add_handler(CallbackQueryHandler(admin_receive_service_content_type, pattern="^service_content_type_"))
    
    # Admin Price Management
    application.add_handler(CallbackQueryHandler(admin_set_service_prices_entry, pattern="^admin_set_service_prices$"))
    application.add_handler(CallbackQueryHandler(admin_set_service_price_type, pattern="^set_price_for_"))
    
    # Admin Discount Management
    application.add_handler(CallbackQueryHandler(admin_manage_discounts_entry, pattern="^admin_manage_discounts$"))
    application.add_handler(CallbackQueryHandler(admin_add_discount_code_entry, pattern="^admin_add_discount_code$"))
    application.add_handler(CallbackQueryHandler(admin_delete_discount_code_entry, pattern="^admin_delete_discount_code$"))
    application.add_handler(CallbackQueryHandler(admin_list_discount_codes, pattern="^admin_list_discount_codes$"))

    # Admin Bot Stats
    application.add_handler(CallbackQueryHandler(admin_bot_stats, pattern="^admin_bot_stats$"))

    # Admin Broadcast Message
    application.add_handler(CallbackQueryHandler(admin_broadcast_message_entry, pattern="^admin_broadcast_message_entry$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_broadcast, pattern="^confirm_broadcast$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_broadcast, pattern="^cancel_broadcast$"))
    
    # Admin Purchase Requests Management
    application.add_handler(CallbackQueryHandler(admin_manage_purchase_requests_entry, pattern="^admin_manage_purchase_requests$"))
    application.add_handler(CallbackQueryHandler(admin_view_pending_purchase_requests, pattern="^admin_view_pending_purchase_requests$"))
    application.add_handler(CallbackQueryHandler(admin_view_approved_purchase_requests, pattern="^admin_view_approved_purchase_requests$"))
    application.add_handler(CallbackQueryHandler(admin_process_purchase_request, pattern="^admin_process_purchase_request_"))
    application.add_handler(CallbackQueryHandler(admin_confirm_purchase_action, pattern="^admin_confirm_purchase_deduct$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_purchase_action, pattern="^admin_confirm_purchase_no_deduct$"))
    application.add_handler(CallbackQueryHandler(admin_confirm_purchase_action, pattern="^admin_reject_purchase_request$"))


    # Conversation Handler for Admin flows (combining several admin text inputs)
    admin_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_manage_specific_user, pattern="^admin_manage_specific_user_"), # For credit actions
            CallbackQueryHandler(admin_add_credit_to_user_init, pattern="^admin_add_credit_to_"),
            CallbackQueryHandler(admin_decrease_credit_from_user_init, pattern="^admin_decrease_credit_from_"),
            CallbackQueryHandler(admin_set_service_content_entry, pattern="^admin_set_service_content_entry$"), # For setting service content
            CallbackQueryHandler(admin_set_service_content_type, pattern="^set_service_content_"),
            CallbackQueryHandler(admin_set_service_prices_entry, pattern="^admin_set_service_prices$"), # For setting service prices
            CallbackQueryHandler(admin_set_service_price_type, pattern="^set_price_for_"),
            CallbackQueryHandler(admin_add_discount_code_entry, pattern="^admin_add_discount_code$"), # For discount management
            CallbackQueryHandler(admin_delete_discount_code_entry, pattern="^admin_delete_discount_code$"),
            CallbackQueryHandler(admin_broadcast_message_entry, pattern="^admin_broadcast_message_entry$"), # For broadcast
        ],
        states={
            ADMIN_USER_ADD_CREDIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_credit_amount)],
            ADMIN_SET_SERVICE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_service_content), 
                                        MessageHandler(filters.Document.ALL & ~filters.COMMAND, admin_receive_service_content)],
            ADMIN_SERVICE_FILE_OR_TEXT: [CallbackQueryHandler(admin_receive_service_content_type, pattern="^service_content_type_")],
            ADMIN_SET_SERVICE_PRICE_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_service_price_value)],
            ADMIN_ADD_DISCOUNT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_new_discount_code)],
            ADMIN_DELETE_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_confirm_delete_discount_code)],
            ADMIN_BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_receive_broadcast_message)],
            ADMIN_BROADCAST_CONFIRM: [CallbackQueryHandler(admin_confirm_broadcast, pattern="^confirm_broadcast$|^cancel_broadcast$")],
            # ADMIN_PROCESS_REQUEST state is handled by CallbackQueryHandler directly, not MessageHandler
        },
        fallbacks=[CommandHandler("cancel", cancel_command), CallbackQueryHandler(admin_panel_back_callback, pattern="^admin_panel_back$")],
        map_to_parent={
            ConversationHandler.END: ADMIN_MAIN_MENU # Return to ADMIN_MAIN_MENU after sub-conversations end
        }
    )
    application.add_handler(admin_conv_handler)


    # Run the bot
    print("🤖 ربات VPN با دکمه‌های شیشه‌ای شروع شد...")
    try:
        application.run_polling()
    except Exception as e:
        print(f"خطا در راه‌اندازی ربات: {e}")
        if "Conflict" in str(e):
            print("⚠️ نمونه دیگری از ربات در حال اجرا است. لطفاً چند دقیقه صبر کنید...")
        else:
            print("در حال تلاش مجدد پس از 5 ثانیه...")
            import time
            time.sleep(5)
            # Optionally retry application.run_polling() here or inform user to restart
            # For simplicity, just log and exit if persistent
            print("تلاش مجدد ناموفق. لطفاً ربات را به صورت دستی راه‌اندازی کنید.")


if __name__ == "__main__":
    main()
