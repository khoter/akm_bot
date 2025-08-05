import logging
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, TO_EMAIL, WEBAPP_URL, ALLOWED_USER_IDS

# Логирование
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Команда /start — приветствие и запуск Web App
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"[START] user_id = {user_id}")

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    keyboard = [
        [InlineKeyboardButton("🚛 Оформить заявку", web_app={"url": WEBAPP_URL})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы заполнить форму заявки:",
        reply_markup=reply_markup
    )


# Обработка данных из Web App
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"[DATA RECEIVED] from {user.id}")

    try:
        data = json.loads(update.message.web_app_data.data)
        logger.debug(f"[FORM DATA]: {data}")

        pdf_bytes = fill_pdf(data)
        send_email(pdf_bytes, TO_EMAIL)

        await update.message.reply_text("✅ Заявка успешно отправлена!")
    except Exception as e:
        logger.exception("[ERROR] Ошибка при обработке данных из Web App")
        await update.message.reply_text(f"❌ Ошибка при отправке заявки: {e}")


# Точка входа
def main():
    logger.debug("[BOOT] Запуск бота...")

    app = Application.builder().token(BOT_TOKEN).build()
    logger.debug("[BOT] Бот слушает...")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

    app.run_polling()


if __name__ == "__main__":
    main()









 
