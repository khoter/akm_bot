"""Telegram Web‑App bot
~~~~~~~~~~~~~~~~~~~~~~~
• Принимает данные формы из веб‑приложения (tg.sendData)
• Генерирует PDF на основе template.pdf
• Отправляет PDF на почту (не блокируя event‑loop)
• Отвечает пользователю об успехе / ошибке

Настройки хранятся в config.py  (не коммитить!)
-------------------------------------------------------------------
config.py должен содержать:
    BOT_TOKEN = "123456:ABC…"          # токен @BotFather
    WEBAPP_URL = "https://…/index.html" # URL формы, открываемой кнопкой
    ALLOWED_USER_IDS = {111, 222, …}    # ID, кому доступен бот
    SMTP_HOST = "smtp.example.com"
    SMTP_PORT = 465
    SMTP_LOGIN = "bot@example.com"
    SMTP_PASSWORD = "…"
    EMAIL_TO = ["manager@example.com"]
-------------------------------------------------------------------
Required packages (pip):
    python-telegram-bot >= 22.0  (PTB 22+)
    httpx  (ставится как зависимость)
    pdfrw   (для fill_pdf.py)
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf          # ваша функция генерации PDF
from email_sender import send_email    # ваша функция отправки письма

# ──────────────────────────── ЛОГИ ────────────────────────────────
LOG_FORMAT = "% (asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE = "bot.log"

root = logging.getLogger()
root.setLevel(logging.INFO)            # базовый уровень (консоль)

# Файл‑хендлер с DEBUG + ротация (10 × 1 МБ)
file_h = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=10, encoding="utf-8")
file_h.setFormatter(logging.Formatter(LOG_FORMAT))
file_h.setLevel(logging.DEBUG)
root.addHandler(file_h)

console_h = logging.StreamHandler()
console_h.setFormatter(logging.Formatter(LOG_FORMAT))
console_h.setLevel(logging.INFO)
root.addHandler(console_h)

# Приглушаем «болтливые» библиотеки
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ─────────────────────── ХЕНДЛЕРЫ ────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start – показывает кнопку для запуска Web‑App"""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔️ У вас нет доступа к использованию формы.")
        logger.warning("[ACCESS DENIED] User %s не в ALLOWED_USER_IDS", user_id)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Оформить заявку", web_app={"url": WEBAPP_URL})]
    ])
    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку ниже, чтобы заполнить заявку:",
        reply_markup=keyboard,
    )
    logger.debug("Кнопка Web‑App отправлена пользователю %s", user_id)


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Получаем данные из формы, генерируем PDF и отправляем письмо"""

    # фильтр уже гарантирует, что web_app_data есть → просто берём
    raw: str = update.message.web_app_data.data  # type: ignore[assignment]
    logger.debug("RAW DATA: %s", raw)

    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Неверный JSON: %s", exc)
        await update.effective_chat.send_message("⚠️ Не удалось прочитать данные формы.")
        return

    try:
        # Путь для PDF
        os.makedirs("output", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        pdf_path = f"output/form_{update.effective_user.id}_{stamp}.pdf"

        # Генерируем PDF
        fill_pdf("template.pdf", pdf_path, data)

        # Отправляем письмо в пуле потоков (чтобы не блокировать asyncio)
        subject = f"Заявка от {data.get('person', 'неизвестно')}"
        body = "В приложении заявка, отправленная через Telegram‑бот."
        await asyncio.to_thread(send_email, subject, body, pdf_path)

        # Ответ пользователю
        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка %s отправлена", pdf_path)

    except Exception as exc:
        logger.exception("Ошибка обработки заявки: %s", exc)
        await update.effective_chat.send_message("❌ Не удалось отправить заявку.")


async def dump(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """DEBUG: выводит сырые апдейты на уровень DEBUG"""
    logger.debug("UPDATE: %s", update)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Логируем все необработанные исключения"""
    logger.exception("Exception while handling update %s", update, exc_info=context.error)


# ─────────────────────────── main() ──────────────────────────────
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    # ↓ уберите, если не нужен дамп
    application.add_handler(MessageHandler(filters.ALL, dump))

    application.add_error_handler(error_handler)

    logger.info("🚀 Бот запущен…")
    application.run_polling()


if __name__ == "__main__":
    main()









 
