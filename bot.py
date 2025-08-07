"""Telegram Web‑App bot
~~~~~~~~~~~~~~~~~~~~~~
Принимает данные формы из Web‑App, генерирует PDF, отправляет письмо.
"""
from __future__ import annotations

import os, json, asyncio, logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from telegram import Update, ReplyKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS, REPORT_CHAT_ID, REPORT_TOPIC_ID
from fill_pdf import fill_pdf
from email_sender import send_email

START_BTN = "🚀 Начать"
FORM_BTN  = "📝 Оформить заявку"

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

# ────────────────────────── КЛАВИАТУРЫ ───────────────────────
START_KB = ReplyKeyboardMarkup([[START_BTN]], resize_keyboard=True, one_time_keyboard=True)
MENU_KB = ReplyKeyboardMarkup(
    [[KeyboardButton(text=FORM_BTN, web_app=WebAppInfo(url=WEBAPP_URL))]],
    resize_keyboard=True,
)

# ─────────────────────── ХЕНДЛЕРЫ ──────────────────────────
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку, чтобы начать.", reply_markup=START_KB
    )


async def handle_start_button(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if update.message.text != START_BTN:
        return
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text(
            "⛔️ У вас нет доступа.", reply_markup=ReplyKeyboardRemove()
        )
        logger.warning("[ACCESS DENIED] %s", user_id)
        return

    await update.message.reply_text("Выберите действие:", reply_markup=MENU_KB)
    logger.debug("Menu shown to %s", user_id)


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.web_app_data.data  # type: ignore[attr-defined]
    logger.debug("RAW DATA: %s", raw)
    
    if 'date' in data:
        try:
            d = datetime.strptime(data['date'], '%Y-%m-%d')
            data['date'] = d.strftime('%d.%m.%Y')    # 07.08.2025
        except ValueError:
            pass

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
        subject = f"Заявка на пропуск от ООО \"АК Микротех\""
        body    = "Здравствуйте! \n К данному письму прилагается заявка на пропуск для транспортного средства!"
        await asyncio.to_thread(send_email, subject, body, pdf_path)
        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка %s отправлена", pdf_path)
    except Exception as exc:
        logger.exception("Ошибка обработки заявки: %s", exc)
        await update.effective_chat.send_message("❌ Не удалось отправить заявку.")

    try:
        text = (
            "📝 *Новая заявка*\n"
            f"• Дата: {data.get('date')}\n"
            f"• Время: {data.get('time_range')}\n"
            f"• Компания: {data.get('company')}\n"
            f"• Транспорт: {data.get('car_model')} / {data.get('car_plate')}\n"
            f"• Груз: {data.get('cargo')} × {data.get('cargo_count')}\n"
            f"• Сотрудник: {data.get('person')}\n"
        )
        await context.bot.send_document(
            chat_id=REPORT_CHAT_ID,
            message_thread_id=REPORT_TOPIC_ID,
            document=open(pdf_path, "rb"),
            filename=os.path.basename(pdf_path),
            caption=text,
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error("Не удалось отправить отчёт в чат: %s", exc)


async def dump(update: Update, _: ContextTypes.DEFAULT_TYPE):
    logger.debug("UPDATE: %s", update)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Exception while handling update %s", update, exc_info=context.error)


# ────────────────────────── main ───────────────────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{START_BTN}$"), handle_start_button))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.ALL, dump))  
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен…")
    app.run_polling()


if __name__ == "__main__":
    main()











 
