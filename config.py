#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration module for VPN Telegram Bot
Contains all configuration constants and state definitions.
"""

import os

# Conversation states
# User flow states (extended from previous version)
REQUESTING_CONTACT = 1
REQUESTING_FULL_NAME = 2
SELECTING_OS = 3
SELECTING_ACCOUNT_TYPE = 4
SELECTING_DEVICE = 5
SELECTING_SERVICE = 6
ENTERING_DISCOUNT_CODE = 7
ENTERING_SUPPORT_MESSAGE = 8
SENDING_ACCOUNT_DETAILS = 9 # For when admin needs to send details
SELECTING_PURCHASE_ACCOUNT_TYPE = 10 # For the user's purchase flow
TRANSFER_USER_ID = 11
TRANSFER_AMOUNT = 12

# Admin flow states (extended and re-indexed for better organization)
ADMIN_MAIN_MENU = 100
ADMIN_USERS = 101
ADMIN_SERVICES = 102
ADMIN_APPROVE_USER = 103 # For specific user approval action
ADMIN_REJECT_USER = 104 # For specific user rejection action
ADMIN_ADD_CREDIT = 105 # Deprecated, now part of ADMIN_USER_DETAIL_VIEW
ADMIN_ADD_CREDIT_AMOUNT = 106
ADMIN_SET_SERVICE = 107 # For selecting service type to set content
ADMIN_SET_SERVICE_PRICE_TYPE = 108 # For selecting service type to set price
ADMIN_SET_SERVICE_PRICE_VALUE = 109 # For inputting service price value
ADMIN_DISCOUNT_CODES = 110 # Main menu for discount codes
ADMIN_ADD_DISCOUNT = 111 # Deprecated, now part of ADMIN_DISCOUNT_CODES
ADMIN_ADD_DISCOUNT_VALUE = 112 # For inputting new discount code and value
ADMIN_DELETE_DISCOUNT = 113 # For deleting discount code
ADMIN_SELECT_USER_FOR_ACTION = 114 # Generic state for selecting a user for admin action (e.g., credit)
ADMIN_CONFIRM_USER_ACTION = 115 # For confirming admin action on a user
ADMIN_TRANSFER_CREDIT_AMOUNT = 116 # Admin transferring credit to user
ADMIN_TRANSFER_CREDIT_TO_USER = 117 # Admin transfer credit: target user input
ADMIN_BROADCAST_MESSAGE = 118 # For inputting broadcast message
ADMIN_BROADCAST_CONFIRM = 119 # For confirming broadcast message
ADMIN_MANAGE_USERS_MENU = 120 # Specific menu for user management
ADMIN_USER_DETAIL_VIEW = 121 # View for specific user details in admin panel
ADMIN_USER_ADD_CREDIT_AMOUNT = 122 # For specific credit amount input
ADMIN_MANAGE_SERVICES_MENU = 123 # Specific menu for service management
ADMIN_SET_SERVICE_CONTENT = 124 # For receiving service content (file/text)
ADMIN_SERVICE_FILE_OR_TEXT = 125 # For choosing if service content is file or text
ADMIN_REQUESTS_MENU = 126 # Menu for managing purchase requests
ADMIN_VIEW_PENDING_REQUESTS = 127 # View pending purchase requests
ADMIN_VIEW_APPROVED_REQUESTS = 128 # View approved purchase requests
ADMIN_PROCESS_REQUEST = 129 # Process a specific purchase request


# Bot configuration
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Asset paths
ASSETS_DIR = "assets"
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
CONFIGS_DIR = os.path.join(ASSETS_DIR, "configs")

# Ensure directories exist
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(CONFIGS_DIR, exist_ok=True)

# App download links
APP_LINKS = {
    "android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
    "ios": "https://apps.apple.com/us/app/openvpn-connect/id590283767",
    "windows": "https://openvpn.net/client-connect-vpn-for-windows/"
}

# Account types and their approximate price (for initial setup, actual prices from DB)
ACCOUNT_TYPES = {
    "1 ماهه (30 روز)": 3000,
    "3 ماهه (90 روز)": 7500,
    "6 ماهه (180 روز)": 12000,
    "1 ساله (365 روز)": 20000,
    "اکانت ویژه (V2Ray)": 5000, # Example price
    "اکسس پوینت (Proxy)": 1000 # Example price
}

# Service types (used for admin to set content/price, and for user request)
SERVICE_TYPES = {
    "OpenVPN": "openvpn",
    "V2Ray": "v2ray",
    "Proxy تلگرام": "proxy"
}

# Device types (for user registration and guide)
DEVICE_TYPES = {
    "اندروید": "android",
    "آیفون": "ios", 
    "ویندوز": "windows",
    "راهنمای اتصال": "guide" # This is a special type for help menu, not an OS for registration
}

# Connection guide images and captions for OpenVPN
CONNECTION_GUIDE = {
    "images": [
        "photo1.jpg", "photo2.jpg", "photo3.jpg", "photo4.jpg", "photo5.jpg",
        "photo6.jpg", "photo7.jpg", "photo8.jpg", "photo9.jpg", "photo10.jpg"
    ],
    "captions": [
        "1. برنامه OpenVPN را از استور نصب کنید و با زدن دکمه تایید وارد برنامه شوید پس از نصب، برنامه را باز کنید.",
        "2. روی تب file کلیک کنید.",
        "3. روی browse کلیک کنید.",
        "4. پوشه‌ای که فایل دریافتی را ذخیره کرده‌اید بروید.",
        "5. فایل دریافتی را انتخاب و وارد برنامه کنید.",
        "6. روی ok کلیک کنید.",
        "7. username و password دریافتی را در قسمت مشخص شده وارد کنید.",
        "8. درخواست اتصال را تایید کنید.",
        "9. اگر متصل نشد روی دکمه کنار فایل کلیک کنید و منتظر بمانید.",
        "10. پس از اتصال موفقیت‌آمیز، وضعیت را سبز ببینید\nبرای قطع اتصال، دکمه را دوباره فشار دهید\nدر صورت بروز مشکل، ابتدا برنامه را ببندید و سپس مراحل را از ابتدا تکرار کنید. اگر مشکل ادامه داشت، با پشتیبانی تماس بگیرید."
    ],
    "additional_note": "لطفاً توجه داشته باشید که برای اتصال به OpenVPN، به نام کاربری و رمز عبور نیاز دارید که پس از تأیید خرید سرویس توسط ادمین، برای شما ارسال خواهد شد."
}
