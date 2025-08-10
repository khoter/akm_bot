import os
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
FROM_EMAIL = os.getenv("FROM_EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")
WEBAPP_URL = os.getenv("WEBAPP_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_IDS = [int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()]
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID")
REPORT_TOPIC_ID = os.getenv("REPORT_TOPIC_ID")
STATUS_CHAT_ID = REPORT_CHAT_ID
STATUS_TOPIC_ID = os.getenv("STATUS_TOPIC_ID")
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "akmicrotech.ru")