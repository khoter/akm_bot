import os
import json
import logging
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

TEMPLATE_PATH = "template.pdf"
TEMP_OUTPUT_PATH = "filled_form.pdf"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔️ У вас нет доступа к использованию бота.")
        return

    keyboard = [[KeyboardButton(text="📝 Оформить заявку", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Нажмите кнопку ниже, чтобы заполнить форму:", reply_markup=reply_markup)

# Обработка данных из WebApp
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔️ У вас нет доступа.")
        return

    try:
        data = json.loads(update.message.web_app_data.data)
        logger.debug(f"[DATA RECEIVED] from {user_id}")
        logger.debug(f"[FORM DATA]: {data}")

        # Заполнение PDF
        fill_pdf(TEMPLATE_PATH, TEMP_OUTPUT_PATH, data)
        logger.debug("[PDF GENERATED]")

        # Отправка email
        subject = "Заявка на пропуск"
        body = "Прикреплен файл с заявкой из Telegram WebApp."
        send_email(subject, body, TEMP_OUTPUT_PATH)
        logger.debug("[EMAIL SENT]")

        await update.message.reply_text("✅ Заявка успешно отправлена!")

    except Exception as e:
        logger.exception("[ERROR] Ошибка при обработке данных из Web App")
        await update.message.reply_text(f"❌ Ошибка при отправке заявки: {e}")

# Запуск
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()








 
