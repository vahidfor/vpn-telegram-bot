import sqlite3

def get_user_info(telegram_id):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT full_name, phone, os, approved, credit FROM users WHERE telegram_id=?", (telegram_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_user_field(telegram_id, field, value):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute(f"UPDATE users SET {field} = ? WHERE telegram_id = ?", (value, telegram_id))
    conn.commit()
    conn.close()

def adjust_credit(telegram_id, amount):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET credit = credit + ? WHERE telegram_id = ?", (amount, telegram_id))
    conn.commit()
    conn.close()

def set_price(service_name, price):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE service_prices SET price = ? WHERE service = ?", (price, service_name))
    conn.commit()
    conn.close()

def get_price(service_name):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("SELECT price FROM service_prices WHERE service = ?", (service_name,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None
