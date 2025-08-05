import os
import json
import logging
from datetime import datetime
from telegram import Update, WebAppData
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from fill_pdf import fill_pdf
from email_sender import send_email

# --- Конфигурация ---
TOKEN = 'YOUR_TOKEN'
OUTPUT_DIR = 'output'
EMAIL_TO = 'info.sky@iqsrv.ru'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Логирование ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"[START] user_id = {update.effective_user.id}")
    await update.message.reply_text(
        "Откройте форму заявки:",
        reply_markup={
            "inline_keyboard": [[
                {"text": "Открыть форму", "web_app": {"url": "https://marsusya.ru/telegram-form/"}}
            ]]
        }
    )

# --- Обработка данных из формы ---
async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        data = json.loads(update.web_app_data.data)
        logger.info(f"[FORM] Данные от {user.username}: {data}")

        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.id}.pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        fill_pdf(data, filepath)
        logger.info(f"[PDF] Сохранено: {filepath}")

        send_email(filepath, to=EMAIL_TO)
        logger.info(f"[EMAIL] Отправлено на {EMAIL_TO}")

        await update.message.reply_text("✅ Заявка получена. PDF отправлен на почту УК.")
    except Exception as e:
        logger.exception("[ERROR] Ошибка обработки формы")
        await update.message.reply_text("❌ Произошла ошибка при обработке заявки.")

# --- Основной запуск ---
def main():
    logger.info("[INIT] Запуск бота...")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    logger.info("[INIT] Хендлеры добавлены. Ожидание сообщений...")
    app.run_polling()

if __name__ == "__main__":
    main()







 
