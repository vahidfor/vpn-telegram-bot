import sqlite3

def get_user(id):
    c = sqlite3.connect("vpn_bot.db").cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (id,))
    return c.fetchone()

def update_user_info(id, name, phone, os):
    conn=sqlite3.connect("vpn_bot.db");c=conn.cursor()
    c.execute("UPDATE users SET full_name=?,phone=?,os=? WHERE telegram_id=?", (name, phone, os, id))
    conn.commit();conn.close()
