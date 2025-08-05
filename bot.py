import json
import logging
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, TO_EMAIL, WEBAPP_URL, ALLOWED_USER_IDS

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def is_user_allowed(user_id):
    return user_id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_allowed(user_id):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    keyboard = [
        [InlineKeyboardButton("🚋 Оформить заявку", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы заполнить форму заявки:",
        reply_markup=reply_markup
    )


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"[DATA RECEIVED] from {user_id}")

    if not is_user_allowed(user_id):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    try:
        raw_data = update.message.web_app_data.data
        data = json.loads(raw_data)
        logger.debug(f"[FORM DATA]: {data}")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            fill_pdf(tmp_pdf.name, data)
            tmp_pdf.seek(0)
            pdf_bytes = tmp_pdf.read()

        send_email(pdf_bytes, TO_EMAIL)
        await update.message.reply_text("✅ Заявка успешно отправлена!")

    except Exception as e:
        logger.exception("[ERROR] Ошибка при обработке данных из Web App")
        await update.message.reply_text(f"❌ Ошибка при отправке заявки: {e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.UpdateType.MESSAGE & filters.HasWebAppData(), handle_web_app_data))
    app.run_polling()


if __name__ == "__main__":
    main()









 
