import os
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from telegram import Update, WebAppData, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import asyncio

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf
from email_sender import send_email

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE   = "bot.log"

root = logging.getLogger()
root.setLevel(logging.INFO)        # базовый уровень

# Файл с ротацией
file_h = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=10, encoding="utf-8")
file_h.setFormatter(logging.Formatter(LOG_FORMAT))
file_h.setLevel(logging.DEBUG)     # подробные логи — в файл
root.addHandler(file_h)

# Коротко в консоль
console_h = logging.StreamHandler()
console_h.setFormatter(logging.Formatter(LOG_FORMAT))
console_h.setLevel(logging.INFO)
root.addHandler(console_h)

# Приглушаем болтливые библиотеки
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext._application").setLevel(logging.WARNING)

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
    # ⚠️ сначала убеждаемся, что это именно данные формы
    if not (update.message and update.message.web_app_data):
        return
    data_msg = update.message.web_app_data          # тут уже гарантировано, что он есть
    try:
        data = json.loads(data_msg.data)
    except json.JSONDecodeError as e:
        logger.error("Не удалось разобрать JSON: %s", e)
        await update.effective_chat.send_message("⚠️ Неверный формат данных формы.")
        return

    # PDF + письмо в отдельном потоке, чтобы не блокировать event-loop
    try:
        os.makedirs("output", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        pdf_path = f"output/form_{update.effective_user.id}_{stamp}.pdf"
        fill_pdf("template.pdf", pdf_path, data)

        await asyncio.to_thread(send_email,
                                f"Заявка от {data.get('person','неизвестно')}",
                                "В приложении заявка, отправленная через Telegram-бот.",
                                pdf_path)
        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка %s отправлена", pdf_path)
    except Exception:
        logger.exception("Ошибка при обработке заявки")
        await update.effective_chat.send_message("❌ Не удалось отправить заявку.")


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









 
