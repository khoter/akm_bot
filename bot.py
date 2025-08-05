import os
import json
import logging
from datetime import datetime

from telegram import Update, WebAppData, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf
from email_sender import send_email

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# --- Стартовая команда ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔️ У вас нет доступа к использованию формы.")
        logger.warning(f"[ACCESS DENIED] User {user_id} не в списке ALLOWED_USER_IDS")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Оформить заявку", web_app={'url': WEBAPP_URL})]
    ])

    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы заполнить заявку:",
        reply_markup=keyboard
    )
    logger.debug(f"[START] Кнопка отправлена пользователю {user_id}")


# --- Обработка данных из Web App ---
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.web_app_data:
        return  # Не web_app_data — пропускаем

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    web_app_data: WebAppData = update.message.web_app_data

    logger.debug(f"[WEB_APP] Получены данные от Telegram:\n{web_app_data.data}")

    if user_id not in ALLOWED_USER_IDS:
        await context.bot.send_message(chat_id=chat_id, text="⛔️ У вас нет доступа к использованию формы.")
        logger.warning(f"[ACCESS DENIED] User {user_id} не в списке ALLOWED_USER_IDS")
        return

    try:
        data = json.loads(web_app_data.data)
        logger.debug(f"[WEB_APP] Данные успешно разобраны: {data}")

        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = f"output/form_{user_id}_{timestamp}.pdf"

        fill_pdf("template.pdf", output_path, data)
        logger.info(f"[PDF] Файл заявки создан: {output_path}")

        subject = f"Заявка от {data.get('person', 'неизвестно')}"
        body = "В приложении заявка, отправленная через Telegram-бот."

        send_email(subject, body, output_path)
        logger.info(f"[EMAIL] Заявка отправлена на {output_path}")

        await context.bot.send_message(chat_id=chat_id, text="✅ Заявка успешно отправлена!")

    except Exception as e:
        logger.exception("[ERROR] Ошибка при обработке заявки:")
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Ошибка при отправке: {e}")


# --- Главная функция ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Хендлер для web_app_data
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE, handle_web_app_data))

    logger.info("🚀 Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()









 
