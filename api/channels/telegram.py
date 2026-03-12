import structlog
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings

MSG_UNAUTHORIZED = "Unauthorized"
MSG_RECEIVED = "Received"

log = structlog.get_logger()

WAITING_FOR_PHOTOS = 0
KEY_PHOTO_FILE_IDS = "photo_file_ids"


def is_correct_chat(chat_id: int | str) -> bool:
    return str(chat_id) == settings.telegram_allowed_chat_id


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return
    if not is_correct_chat(chat.id):
        await message.reply_text(MSG_UNAUTHORIZED)
        return

    log.info("message_received", chat_id=chat.id, text=message.text)
    await message.reply_text(MSG_RECEIVED)


async def start_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END
    log.info("teach_started", chat_id=update.effective_chat.id if update.effective_chat else None)

    context.user_data[KEY_PHOTO_FILE_IDS] = []
    await message.reply_text("Schicke mir deine Fotos! Wenn du fertig bist, sende /done")

    return WAITING_FOR_PHOTOS


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None or not message.photo:
        return WAITING_FOR_PHOTOS

    file_id = message.photo[-1].file_id
    context.user_data[KEY_PHOTO_FILE_IDS].append(file_id)

    count = len(context.user_data[KEY_PHOTO_FILE_IDS])
    log.info("teach_photo_received", file_id=file_id, total=count)

    return WAITING_FOR_PHOTOS


async def finish_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END
    file_ids = context.user_data.get(KEY_PHOTO_FILE_IDS, [])

    if not file_ids:
        await message.reply_text("Du hast keine Fotos geschickt. Bitte starte mit /teach erneut.")
        return ConversationHandler.END

    log.info("teach_finished", file_ids=file_ids, count=len(file_ids))

    # TODO: hand file_ids to downstream processing service
    await message.reply_text(f"Danke! {len(file_ids)} Foto(s) empfangen. Verarbeitung startet....")

    context.user_data.pop(KEY_PHOTO_FILE_IDS, None)
    return ConversationHandler.END


async def cancel_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END

    context.user_data.pop(KEY_PHOTO_FILE_IDS, None)
    log.info("teach_cancelled")

    await message.reply_text("Abgebrochen")
    return ConversationHandler.END


async def timeout_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is not None:
        context.user_data.pop(KEY_PHOTO_FILE_IDS, None)
    log.info("teach_timed_out")


def build_app():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    teach_conv = ConversationHandler(
        entry_points=[CommandHandler("teach", start_teach)],
        states={
            WAITING_FOR_PHOTOS: [
                MessageHandler(filters.PHOTO, collect_photo),
                CommandHandler("done", finish_teach),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout_teach),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_teach)],
        conversation_timeout=300,
    )

    app.add_handler(teach_conv)
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    return app
