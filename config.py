import os
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
FROM_EMAIL = os.getenv("FROM_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_CHAT_IDS = [int(id.strip()) for id in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if id.strip()]
ALLOWED_USER_IDS = [int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()]