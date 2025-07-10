import os
from dotenv import load_dotenv
from telegram.ext import Application
from keep_alive import keep_alive
from handlers.user_handlers import setup_user_handlers
from handlers.admin_handlers import setup_admin_handlers
from database import init_db

load_dotenv()
keep_alive()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

app = Application.builder().token(TOKEN).build()
init_db()
setup_user_handlers(app)
setup_admin_handlers(app)

if __name__ == "__main__":
    app.run_polling()
