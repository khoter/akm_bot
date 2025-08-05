import json
import logging
import os
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, TO_EMAIL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf
from email_sender import send_email

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"⛔ Недопустимый пользователь {user_id}")
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    keyboard = [[
        KeyboardButton(text="📝 Оформить заявку", web_app=WebAppInfo(url="https://marsusya.ru/telegram-form/"))
    ]]
    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы заполнить форму заявки",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        logger.warning(f"⛔ Данные от недопустимого пользователя {user_id}")
        await update.message.reply_text("⛔ У вас нет доступа к этому действию.")
        return

    if not update.message.web_app_data:
        return

    try:
        logger.debug(f"[DATA RECEIVED] from {user_id}")

        raw_data = update.message.web_app_data.data
        data = json.loads(raw_data)
        logger.debug(f"[FORM DATA]: {data}")

        output_path = f"output/{user_id}_{data['date']}.pdf"
        os.makedirs("output", exist_ok=True)

        pdf_bytes = fill_pdf(output_path, data)
        send_email(pdf_bytes, TO_EMAIL)

        await update.message.reply_text("✅ Заявка успешно отправлена!")
    except Exception as e:
        logger.exception("[ERROR] Ошибка при обработке данных из Web App")
        await update.message.reply_text(f"❌ Ошибка при отправке заявки: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.UpdateType.MESSAGE, handle_web_app_data))
    app.run_polling()

if __name__ == "__main__":
    main()









 
