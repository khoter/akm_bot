"""Telegram Web‑App bot
~~~~~~~~~~~~~~~~~~~~~~
Принимает данные формы из Web‑App, генерирует PDF, отправляет письмо.
"""
from __future__ import annotations

import os, json, asyncio, logging, re
from datetime import datetime, timezone, time
from time import perf_counter
from logging.handlers import RotatingFileHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, ReplyKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
)

from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_USER_IDS, REPORT_CHAT_ID, REPORT_TOPIC_ID, STATUS_CHAT_ID, STATUS_TOPIC_ID, EMAIL_DOMAIN
from fill_pdf import fill_pdf
from email_sender import send_email

# ────────────────────────── КОНСТАНТЫ ────────────────────────────
START_BTN = "🚀 Начать"
FORM_BTN  = "📝 Оформить заявку"
STOP_BTN  = "🛑 Остановить бота"
MANUAL_BTN = "🧰 Ручной режим"

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

def yn_to_bool(text: str) -> bool:
    return text.strip().lower() in ("да", "yes", "y", "д", "угу")

# ────────────────────────── КЛАВИАТУРЫ ───────────────────────
START_KB = ReplyKeyboardMarkup([[START_BTN, MANUAL_BTN]], resize_keyboard=True, one_time_keyboard=True)
YES_NO_KB = ReplyKeyboardMarkup([["Да", "Нет"]], resize_keyboard=True)

# ─────────────────────── ХЕНДЛЕРЫ ──────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать! Нажмите кнопку, чтобы начать или выберите ручной режим.",
        reply_markup=START_KB
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
    if not update.message or not update.message.web_app_data:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in ALLOWED_USER_IDS:
        await context.bot.send_message(chat_id=chat_id, text="⛔️ У вас нет доступа к использованию формы.")
        logger.warning("[ACCESS DENIED] user_id=%s не в ALLOWED_USER_IDS", user_id)
        return
    
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

    cc_list = []
    mail3 = str(data.get("mail3", "")).strip().lower()
    if mail3:
        if re.fullmatch(r"[a-z]{3}", mail3):
            cc_email = f"{mail3}@{EMAIL_DOMAIN}"
            cc_list.append(cc_email)
            logger.info("CC email: %s", cc_email)
        else:
            logger.warning("Игнорирую некорректное mail3=%r", mail3)

    try:
        os.makedirs("output", exist_ok=True)

        async with PDF_LOCK:
            fill_pdf("template.pdf", PDF_TMP_PATH, data)
            os.replace(PDF_TMP_PATH, PDF_PATH)

        subject = 'Заявка на пропуск от ООО "АК Микротех"'
        body    = "Здравствуйте!\nК данному письму прилагается заявка на пропуск для транспортного средства."

        await asyncio.to_thread(send_email, subject, body, PDF_PATH, cc=cc_list)

        await update.effective_chat.send_message("✅ Заявка успешно отправлена!")
        logger.info("Заявка сохранена в %s и отправлена. CC=%s", PDF_PATH, cc_list)

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
                document=f,
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

(
    DATE, TIME, COMPANY, CAR_MODEL, CAR_PLATE, CARGO, CARGO_COUNT, PERSON, MAIL3,
    USE_LIFT, MATERIALS_IN, MATERIALS_OUT, UNLOADING_BIG, LOADING_BIG, UNLOADING_SMALL, LOADING_SMALL
) = range(16)

async def start_manual_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ У вас нет доступа к заполнению формы.")
        return ConversationHandler.END

    await update.message.reply_text("📅 Введите дату (ДД.ММ.ГГГГ):", reply_markup=ReplyKeyboardRemove())
    return DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            dt = datetime.strptime(raw, "%Y-%m-%d")
        else:
            dt = datetime.strptime(raw, "%d.%m.%Y")
        context.user_data["date"] = dt.strftime("%d.%m.%Y")
    except Exception:
        await update.message.reply_text("⚠️ Формат даты не распознан. Введите в виде ДД.ММ.ГГГГ.")
        return DATE

    await update.message.reply_text("⏰ Введите время (например: 10:00 - 18:00):")
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time_range"] = update.message.text.strip()
    await update.message.reply_text("🏢 Введите название компании:")
    return COMPANY

async def get_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["company"] = update.message.text.strip()
    await update.message.reply_text("🚚 Введите модель автомобиля:")
    return CAR_MODEL

async def get_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["car_model"] = update.message.text.strip()
    await update.message.reply_text("🔢 Введите госномер автомобиля:")
    return CAR_PLATE

async def get_car_plate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["car_plate"] = update.message.text.strip()
    await update.message.reply_text("📦 Что за груз?")
    return CARGO

async def get_cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cargo"] = update.message.text.strip()
    await update.message.reply_text("📦 Укажите количество груза (число):")
    return CARGO_COUNT

async def get_cargo_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["cargo_count"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠ Введите число!")
        return CARGO_COUNT
    await update.message.reply_text("👤 ФИО сопровождающего:")
    return PERSON

async def get_person(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["person"] = update.message.text.strip()
    await update.message.reply_text("📧 Введите первые 3 буквы вашей почты (или оставьте пустым):")
    return MAIL3

async def get_mail3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mail3 = update.message.text.strip().lower()
    if mail3:
        if re.fullmatch(r"[a-z]{3}", mail3):
            context.user_data["mail3"] = mail3
        else:
            await update.message.reply_text("⚠️ Введите ровно 3 латинские буквы или оставьте пустым. Повторите ввод:")
            return MAIL3

    await update.message.reply_text("📦 Используется ли лифт?", reply_markup=YES_NO_KB)
    return USE_LIFT


async def get_use_lift(update, context):
    context.user_data["use_lift"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Материалы вносятся?", reply_markup=YES_NO_KB)
    return MATERIALS_IN

async def get_materials_in(update, context):
    context.user_data["materials_in"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Материалы выносятся?", reply_markup=YES_NO_KB)
    return MATERIALS_OUT

async def get_materials_out(update, context):
    context.user_data["materials_out"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Выгрузка крупногабаритного?", reply_markup=YES_NO_KB)
    return UNLOADING_BIG

async def get_unloading_big(update, context):
    context.user_data["unloading_big"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Погрузка крупногабаритного?", reply_markup=YES_NO_KB)
    return LOADING_BIG

async def get_loading_big(update, context):
    context.user_data["loading_big"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Выгрузка мелкогабаритного?", reply_markup=YES_NO_KB)
    return UNLOADING_SMALL

async def get_unloading_small(update, context):
    context.user_data["unloading_small"] = yn_to_bool(update.message.text)
    await update.message.reply_text("📦 Погрузка мелкогабаритного?", reply_markup=YES_NO_KB)
    return LOADING_SMALL

async def get_loading_small(update, context):
    context.user_data["loading_small"] = yn_to_bool(update.message.text)
    await process_form(update, context)
    return ConversationHandler.END

async def process_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data.copy()

    cc_list = []
    m3 = data.get("mail3")
    if m3:
        cc_list.append(f"{m3}@{EMAIL_DOMAIN}")

    os.makedirs("output", exist_ok=True)
    output_path = "output/form_latest.pdf"

    fill_pdf("template.pdf", output_path, data)

    subject = 'Заявка на пропуск от ООО "АК Микротех"'
    body = "Здравствуйте!\nК данному письму прилагается заявка на пропуск для транспортного средства."
    await asyncio.to_thread(send_email, subject, body, output_path, cc=cc_list)

    await update.message.reply_text("✅ Заявка успешно отправлена!", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Заполнение формы отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ────────────────────────── HEARTBEAT ──────────────────────────
async def heartbeat(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot 
    start = context.job.data["start"]
    now   = datetime.now(timezone.utc)
    uptime = now - start

    # ping
    t0 = perf_counter()
    await bot.get_me()
    ping_ms = int((perf_counter() - t0) * 1000)

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

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("manual_form", start_manual_form),
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(MANUAL_BTN)}$"), start_manual_form),
        ],
        states={
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_company)],
            CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_model)],
            CAR_PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_plate)],
            CARGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cargo)],
            CARGO_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cargo_count)],
            PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_person)],
            MAIL3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mail3)],
            USE_LIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_use_lift)],
            MATERIALS_IN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_materials_in)],
            MATERIALS_OUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_materials_out)],
            UNLOADING_BIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_unloading_big)],
            LOADING_BIG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loading_big)],
            UNLOADING_SMALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_unloading_small)],
            LOADING_SMALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_loading_small)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv, group=0)

    app.add_handler(CommandHandler("start", cmd_start), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{START_BTN}$"), handle_start_button), group=1)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{STOP_BTN}$"), handle_stop), group=1)
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data), group=1)
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(heartbeat, interval=1200, first=0, data={"start": START_TIME})
    app.run_polling()

if __name__ == "__main__":
    main()