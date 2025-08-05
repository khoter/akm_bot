from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, ALLOWED_CHAT_IDS, WEBAPP_URL
from datetime import datetime
import os
import logging
import json
import asyncio

logging.basicConfig(level=logging.DEBUG)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть форму", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await update.message.reply_text("Откройте форму заявки:", reply_markup=keyboard)


# Обработка web_app данных
async def handle_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.debug(f"[HANDLE_WEBAPP] Получен update от user_id={user_id}")
    logging.debug(f"[HANDLE_WEBAPP] Полный update: {update}")

    if user_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("❌ У вас нет доступа к использованию этого бота.")
        return

    web_app_data = update.message.web_app_data
    if not web_app_data:
        logging.warning("[HANDLE_WEBAPP] web_app_data is None!")
        return

    try:
        logging.debug(f"[HANDLE_WEBAPP] web_app_data: {web_app_data.data}")
        data = json.loads(web_app_data.data)

        if not data.get("date"):
            data["date"] = datetime.now().strftime("%d.%m.%Y")

        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"Заявка_{date_str}.pdf")
        template_path = os.path.join(os.path.dirname(__file__), "template.pdf")

        logging.debug("[HANDLE_WEBAPP] Заполнение PDF...")
        fill_pdf(template_path, output_file, data)

        logging.debug("[HANDLE_WEBAPP] Отправка email...")
        send_email("Заявка на пропуск", "Сформирована новая заявка", output_file)

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
            except Exception as e:
                logging.error(f"❗ Не удалось отправить сообщение {admin_id}: {e}")

    except Exception as e:
        logging.exception("❌ Ошибка при обработке данных из web app")
        await update.message.reply_text("❌ Произошла ошибка при обработке заявки.")


if __name__ == "__main__":
    print(f"[DEBUG] BOT_TOKEN: {BOT_TOKEN}")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Фильтр на web_app_data через filters.TEXT
    web_app_filter = filters.TEXT & filters.ChatType.PRIVATE

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(web_app_filter, handle_webapp))

    print("[DEBUG] Бот слушает сообщения...")
    app.run_polling()



 
