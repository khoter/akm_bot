"""Telegram Web‑App bot
~~~~~~~~~~~~~~~~~~~~~~
Принимает данные формы из Web‑App, генерирует PDF, отправляет письмо.
"""
from __future__ import annotations

import os, json, asyncio, logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from telegram import Update, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf
from email_sender import send_email

# ────────────────────────── ЛОГИ ────────────────────────────
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE   = "bot.log"
root = logging.getLogger()
root.setLevel(logging.INFO)
file_h = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=10, encoding="utf-8")
file_h.setFormatter(logging.Formatter(LOG_FORMAT))
file_h.setLevel(logging.DEBUG)
root.addHandler(file_h)
console_h = logging.StreamHandler()
console_h.setFormatter(logging.Formatter(LOG_FORMAT))
console_h.setLevel(logging.INFO)
root.addHandler(console_h)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ─────────────────────── ХЕНДЛЕРЫ ──────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливаем (или убираем) кнопку Web‑App в меню чата"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USER_IDS:
        # сбрасываем кнопку на дефолтное меню
        await context.bot.set_chat_menu_button(chat_id=chat_id, menu_button=None)
        await update.message.reply_text("⛔️ У вас нет доступа к использованию формы.")
        logger.warning("[ACCESS DENIED] user %s", user_id)
        return

    # разрешённый пользователь — персональная кнопка
    await context.bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(
            text="📝 Оформить заявку",
            web_app=WebAppInfo(url=WEBAPP_URL),
        ),
    )
    await update.message.reply_text("Добро пожаловать! Откройте форму через кнопку 🧩 в меню чата.")
    logger.debug("Web‑App‑кнопка установлена для %s", user_id)


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.web_app_data.data  # type: ignore[attr-defined]
    logger.debug("RAW DATA: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Неверный JSON: %s", exc)
        await update.effective_chat.send_message("⚠️ Не удалось прочитать данные формы.")
        return

    try:
        os.makedirs("output", exist_ok=True)
        pdf_path = f"output/form_{update.effective_user.id}_{datetime.now():%Y%m%d%H%M%S}.pdf"
        fill_pdf("template.pdf", pdf_path, data)
        subject = f"Заявка от {data.get('person', 'неизвестно')}"
        body    = "В приложении заявка, отправленная через Telegram‑бот."
        await asyncio.to_thread(send_email, subject, body, pdf_path)
        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка %s отправлена", pdf_path)
    except Exception as exc:
        logger.exception("Ошибка обработки заявки: %s", exc)
        await update.effective_chat.send_message("❌ Не удалось отправить заявку.")


async def dump(update: Update, _: ContextTypes.DEFAULT_TYPE):
    logger.debug("UPDATE: %s", update)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Exception while handling update %s", update, exc_info=context.error)


# ────────────────────────── main ───────────────────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.ALL, dump))  # уберите, если не нужен дамп
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен…")
    app.run_polling()


if __name__ == "__main__":
    main()











 
