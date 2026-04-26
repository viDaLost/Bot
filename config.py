import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db").strip()

_raw_admins = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = []

if _raw_admins:
    ADMIN_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не указан. Создайте файл .env или переменные окружения.")
