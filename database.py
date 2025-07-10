import sqlite3

def init_db():
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.executescript("""
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS discount_codes;
    DROP TABLE IF EXISTS service_prices;
    CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, full_name TEXT, phone TEXT, os TEXT, approved INTEGER DEFAULT 0, credit INTEGER DEFAULT 0);
    CREATE TABLE discount_codes (code TEXT PRIMARY KEY, value INTEGER, used_by INTEGER);
    CREATE TABLE service_prices (service TEXT PRIMARY KEY, price INTEGER);
    INSERT INTO service_prices (service, price) VALUES ('OpenVPN',150),('V2Ray',100),('Proxy',50);
    """)
    conn.commit()
    conn.close()
