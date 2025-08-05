from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from fill_pdf import fill_pdf
from email_sender import send_email
from config import BOT_TOKEN, ALLOWED_CHAT_IDS
import os
from datetime import datetime
import logging

QUESTIONS = [
    "Введите марку автомобиля:",
    "Введите госномер автомобиля:",
    "Укажите сотрудника, который будет принимать/отгружать товар:"
]

FIELD_NAMES = [
    "car_model", "car_plate", "person"
]

DEFAULT_VALUES = {
    "date": datetime.now().strftime("%d.%m.%Y"),
    "time_range": "10:00 - 18:00",
    "company": "ООО \"Деловые линии\"",
    "cargo": "Пленка в рулонах",
    "cargo_count": "4"
}

user_data = {}

logging.basicConfig(level=logging.DEBUG)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("Доступ запрещён.")
        return ConversationHandler.END

    user_data[update.effective_chat.id] = {"step": 0, "answers": {}}
    await update.message.reply_text(QUESTIONS[0])
    return 1

async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = user_data.get(chat_id)

    if not state:
        await update.message.reply_text("Ошибка состояния. Напишите /start")
        return ConversationHandler.END

    step = state["step"]
    state["answers"][FIELD_NAMES[step]] = update.message.text
    step += 1

    if step < len(QUESTIONS):
        state["step"] = step
        await update.message.reply_text(QUESTIONS[step])
        return 1
    else:
        combined = {**DEFAULT_VALUES, **state["answers"]}
        summary = "\n".join(f"{k}: {v}" for k, v in combined.items())
        await update.message.reply_text(f"Подтвердите заявку:\n\n{summary}\n\nВведите /confirm для отправки или /cancel для отмены.")
        return 2

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_answers = user_data.get(chat_id, {}).get("answers", {})

    if not user_answers:
        await update.message.reply_text("Нет данных для отправки.")
        return ConversationHandler.END

    filled_data = {**DEFAULT_VALUES, **user_answers}

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"Заявка_{date_str}.pdf")
    template_path = os.path.join(os.path.dirname(__file__), "template.pdf")

    fill_pdf(template_path, output_file, filled_data)
    send_email("Заявка на пропуск", "Сформирована новая заявка", output_file)

    await update.message.reply_text("✅ Заявка отправлена по почте.")
    user_data.pop(chat_id, None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data.pop(update.effective_chat.id, None)
    await update.message.reply_text("Заявка отменена.")
    return ConversationHandler.END

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect)],
            2: [
                CommandHandler("confirm", confirm),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("Бот запущен")
    app.run_polling()

   
