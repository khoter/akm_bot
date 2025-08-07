"""Telegram Web‑App bot
~~~~~~~~~~~~~~~~~~~~~~
Принимает данные формы из Web‑App, генерирует PDF, отправляет письмо.
"""
from __future__ import annotations

import os, json, asyncio, logging
from datetime import datetime, timezone, time
from logging.handlers import RotatingFileHandler

from telegram import Update, ReplyKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS, REPORT_CHAT_ID, REPORT_TOPIC_ID, STATUS_CHAT_ID, STATUS_TOPIC_ID
from fill_pdf import fill_pdf
from email_sender import send_email

# ────────────────────────── КОНСТАНТЫ ────────────────────────────
START_BTN = "🚀 Начать"
FORM_BTN  = "📝 Оформить заявку"
STOP_BTN  = "🛑 Остановить бота"

ADMIN_ID = ALLOWED_USER_IDS[0]

START_TIME = datetime.now(timezone.utc)

PDF_PATH     = "output/form_latest.pdf"           
PDF_TMP_PATH = "output/.form_latest.tmp.pdf"      
PDF_LOCK     = asyncio.Lock() 

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

# ────────────────────────── ЛОГИ В ТГ ──────────────────────────
class TelegramErrorHandler(logging.Handler):
    def __init__(self, app, chat_id: int, thread_id: int | None = None):
        super().__init__(logging.ERROR)
        self.app = app
        self.chat_id = chat_id
        self.thread_id = thread_id

    def emit(self, record: logging.LogRecord):
        if not getattr(self.app, "running", False):
            return

        msg = self.format(record)

        async def _send():
            try:
                await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    message_thread_id=self.thread_id,
                    text=f"❌ *ERROR*\n```{msg}```",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        try:
            self.app.create_task(_send())
        except Exception:
            pass

# ────────────────────────── ФУНКЦИИ ────────────────────────────
def build_menu_kb(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(FORM_BTN, web_app=WebAppInfo(url=WEBAPP_URL))]]
    if user_id == ADMIN_ID:
        buttons.append([STOP_BTN])                   
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def on_startup(app: Application):
    try:
        await app.bot.send_message(
            chat_id=STATUS_CHAT_ID,
            message_thread_id=STATUS_TOPIC_ID,
            text="✅ Бот *запущен*",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("Не удалось отправить стартовое сообщение: %s", e)

# ────────────────────────── КЛАВИАТУРЫ ───────────────────────
START_KB = ReplyKeyboardMarkup([[START_BTN]], resize_keyboard=True, one_time_keyboard=True)

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

    await update.message.reply_text(
    "Выберите действие:",
    reply_markup=build_menu_kb(user_id)
    )
    logger.debug("Menu shown to %s", user_id)

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.web_app_data.data  
    logger.debug("RAW DATA: %s", raw)
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Неверный JSON: %s", exc)
        await update.effective_chat.send_message("⚠️ Не удалось прочитать данные формы.")
        return
    
    if 'date' in data:
        try:
            d = datetime.strptime(data['date'], '%Y-%m-%d')
            data['date'] = d.strftime('%d.%m.%Y')    
        except ValueError:
            pass
    
    try:
        os.makedirs("output", exist_ok=True)

        async with PDF_LOCK:
            fill_pdf("template.pdf", PDF_TMP_PATH, data)
            os.replace(PDF_TMP_PATH, PDF_PATH)
        
        subject = 'Заявка на пропуск от ООО "АК Микротех"'
        body    = "Здравствуйте!\nК данному письму прилагается заявка на пропуск для транспортного средства."

        await asyncio.to_thread(send_email, subject, body, PDF_PATH)
        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка сохранена в %s и отправлена", PDF_PATH)
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
        with open(PDF_PATH, "rb") as f:
            await context.bot.send_document(
                chat_id=REPORT_CHAT_ID,
                message_thread_id=REPORT_TOPIC_ID,
                document= f,
                filename=os.path.basename(PDF_PATH),
                caption=text,
                parse_mode="Markdown",
            )
    except Exception as exc:
        logger.error("Не удалось отправить отчёт в чат: %s", exc)

async def dump(update: Update, _: ContextTypes.DEFAULT_TYPE):
    logger.debug("UPDATE: %s", update)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Exception while handling update %s", update, exc_info=context.error)

async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        await context.bot.send_message(
            chat_id=STATUS_CHAT_ID,
            message_thread_id=STATUS_TOPIC_ID,
            text="⏹ Бот остановлен *админом*",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await update.message.reply_text("⏹ Останавливаюсь…", reply_markup=ReplyKeyboardRemove())
    logger.warning("Bot stopped by admin %s", ADMIN_ID)

    for h in list(root.handlers):
        if isinstance(h, TelegramErrorHandler):
            root.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

    try:
        jq = context.application.job_queue
        if jq:
            await jq.stop()
    except Exception:
        pass

    context.application.stop_running()

# ────────────────────────── HEARTBEAT ──────────────────────────
async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot 
    start = context.job.data["start"]
    now   = datetime.now(timezone.utc)
    uptime = now - start

    # ping
    t0 = time.perf_counter()
    await bot.get_me()
    ping_ms = int((time.perf_counter() - t0) * 1000)

    msg = (
        "🟢 *Бот жив*\n"
        f"Start: `{start.strftime('%d.%m.%Y %H:%M:%S')} UTC`\n"
        f"Uptime: `{str(uptime).split('.')[0]}`\n"
        f"Ping: `{ping_ms} ms`"
    )
    await bot.send_message(chat_id=STATUS_CHAT_ID, message_thread_id=STATUS_TOPIC_ID, text=msg, parse_mode='Markdown')

# ────────────────────────── main ───────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()

    tg_handler = TelegramErrorHandler(app, STATUS_CHAT_ID, STATUS_TOPIC_ID)
    tg_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(tg_handler)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{START_BTN}$"), handle_start_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{STOP_BTN}$"),  handle_stop))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat, interval=300, first=0, data={"start": START_TIME})

    app.run_polling()

if __name__ == "__main__":
    main()