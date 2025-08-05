import os
import json
import logging
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, WEBAPP_URL, ALLOWED_CHAT_IDS, ALLOWED_USER_IDS

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# /start команда с инлайн-кнопкой (надежный вызов WebApp)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"[START] user_id = {user_id}")

    if user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Заполнить заявку", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text(
        "Нажмите кнопку ниже, чтобы открыть форму заявки:",
        reply_markup=keyboard
    )


# Обработка данных из WebApp
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"[HANDLE_WEBAPP] Получен update: {update}")

    try:
        if not update.message:
            logger.warning("[HANDLE_WEBAPP] ❌ Нет update.message")
            return

        if update.effective_user.id not in ALLOWED_CHAT_IDS:
            await update.message.reply_text("❌ У вас нет доступа.")
            return

        if not update.message.web_app_data:
            logger.warning("[HANDLE_WEBAPP] ❌ Нет web_app_data")
            await update.message.reply_text("❌ Данные не получены.")
            return

        raw_data = update.message.web_app_data.data
        logger.debug(f"[HANDLE_WEBAPP] Получены данные: {raw_data}")

        # Telegram иногда передаёт мусорные символы — удалим
        cleaned_data = ''.join(c for c in raw_data if c >= ' ')
        data = json.loads(cleaned_data)

        logger.debug(f"[HANDLE_WEBAPP] Распарсенные данные: {data}")

        if not data.get("date"):
            data["date"] = datetime.now().strftime("%d.%m.%Y")

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        filename = f"Заявка_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        output_file = os.path.join(output_dir, filename)
        template_file = os.path.join(os.path.dirname(__file__), "template.pdf")

        logger.debug("[PDF] Заполнение PDF...")
        fill_pdf(template_file, output_file, data)
        logger.debug(f"[PDF] Файл сохранён: {output_file}")

        logger.debug("[EMAIL] Отправка email...")
        send_email("Заявка на пропуск", "Сформирована новая заявка", output_file)
        logger.debug("[EMAIL] Успешно отправлено.")

        await update.message.reply_text("✅ Заявка успешно отправлена по почте.")

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
                logger.debug(f"[SEND] Уведомление отправлено в чат {admin_id}")
            except Exception as e:
                logger.error(f"[SEND] ❌ Ошибка при отправке сообщения {admin_id}: {e}")

    except Exception as e:
        logger.exception("❌ Ошибка в обработке WebApp данных")
        if update.message:
            await update.message.reply_text("❌ Ошибка при обработке заявки.")


if __name__ == "__main__":
    logger.debug("[BOOT] Запуск бота...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start
    app.add_handler(CommandHandler("start", start))

    # Обработка только web_app_data
    app.add_handler(MessageHandler(filters.TEXT & filters.UpdateType.MESSAGE, handle_webapp_data))

    logger.debug("[BOT] Бот слушает...")
    app.run_polling()








 
