import os
import json
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

from config import BOT_TOKEN, ALLOWED_CHAT_IDS, WEBAPP_URL, ALLOWED_USER_IDS
from fill_pdf import fill_pdf
from email_sender import send_email

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"[START] user_id = {user_id}")

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть форму", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text("Откройте форму заявки:", reply_markup=keyboard)


async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"[HANDLE_WEBAPP] Пришёл update: {update}")

    try:
        if not update.message:
            logger.warning("[HANDLE_WEBAPP] ❌ Нет update.message — update НЕ содержит сообщение.")
            return

        if update.effective_user.id not in ALLOWED_CHAT_IDS:
            await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
            return

        if not update.message.web_app_data:
            logger.warning("[HANDLE_WEBAPP] ❌ Нет web_app_data.")
            await update.message.reply_text("❌ Данные не получены.")
            return

        raw_data = update.message.web_app_data.data
        logger.debug(f"[HANDLE_WEBAPP] Получены web_app_data: {raw_data}")

        cleaned_data = ''.join(c for c in raw_data if c >= ' ')
        data = json.loads(cleaned_data)

        logger.debug(f"[HANDLE_WEBAPP] Распарсенные данные: {data}")

        if not data.get("date"):
            data["date"] = datetime.now().strftime("%d.%m.%Y")

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"Заявка_{date_str}.pdf")
        template_path = os.path.join(os.path.dirname(__file__), "template.pdf")

        logger.debug("[PDF] Начинаем заполнение PDF...")
        fill_pdf(template_path, output_file, data)
        logger.debug(f"[PDF] PDF сохранён в {output_file}")

        logger.debug("[EMAIL] Пытаемся отправить email...")
        send_email("Заявка на пропуск", "Сформирована новая заявка", output_file)
        logger.debug("[EMAIL] Email успешно отправлен.")

        await update.message.reply_text("✅ Заявка отправлена по почте.")

        summary = (
            f"📩 <b>Заявка отправлена</b>\n\n"
            f"<b>Дата:</b> {data.get('date')}\n"
            f"<b>Время:</b> {data.get('time_range')}\n"
            f"<b>Компания:</b> {data.get('company')}\n"
            f"<b>Груз:</b> {data.get('cargo')} × {data.get('cargo_count')}\n"
            f"<b>Машина:</b> {data.get('car_model')} ({data.get('car_plate')})\n"
            f"<b>Получатель:</b> {data.get('person')}\n\n"
            f"<b>Доп. опции:</b>\n" +
            "\n".join([
                f"• {label}" for key, label in {
                    "use_lift": "Лифт",
                    "materials_in": "Внос МЦ",
                    "materials_out": "Вынос МЦ",
                    "unloading_big": "Разгрузка стройматериалов",
                    "loading_big": "Загрузка стройматериалов",
                    "unloading_small": "Разгрузка мелкогабаритного груза",
                    "loading_small": "Загрузка мелкогабаритного груза"
                }.items() if data.get(key)
            ]) or "—"
        )

        for admin_id in ALLOWED_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=summary, parse_mode="HTML")
                logger.debug(f"[SEND] Отправлено сообщение в чат {admin_id}")
            except Exception as e:
                logger.error(f"[SEND] ❌ Ошибка при отправке сообщения {admin_id}: {e}")

    except Exception as e:
        logger.exception("❌ Ошибка в handle_webapp")
        if update.message:
            await update.message.reply_text("❌ Ошибка при обработке заявки.")


if __name__ == "__main__":
    print(f"[DEBUG] BOT_TOKEN: {BOT_TOKEN}")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Ловим всё подряд, чтобы точно ничего не упустить
    app.add_handler(MessageHandler(filters.ALL, handle_webapp))

    print("[DEBUG] Запускаем бота...")
    app.run_polling()






 
