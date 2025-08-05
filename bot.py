from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.ext import ConversationHandler
from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, ALLOWED_CHAT_IDS, WEBAPP_URL
from datetime import datetime
import os
import logging
import json

logging.basicConfig(level=logging.DEBUG)

# Mini App WebApp URL
WEBAPP_URL = "https://marsusya.ru/telegram-form/"

# Команда /start показывает кнопку для открытия Web App
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть форму", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text("Откройте форму заявки:", reply_markup=keyboard)

# Обработка данных из Web App
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    try:
        data = json.loads(update.message.web_app_data.data)

        if not data.get("date"):
            data["date"] = datetime.now().strftime("%d.%m.%Y")

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"Заявка_{date_str}.pdf")
        template_path = os.path.join(os.path.dirname(__file__), "template.pdf")

        fill_pdf(template_path, output_file, data)
        send_email("Заявка на пропуск", "Сформирована новая заявка", output_file)

        await update.message.reply_text("✅ Заявка отправлена по почте.")
    except Exception as e:
        logging.exception("Ошибка при обработке данных из web app")
        await update.message.reply_text("❌ Произошла ошибка при обработке заявки.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp))

    print("Бот запущен")
    app.run_polling()

   
