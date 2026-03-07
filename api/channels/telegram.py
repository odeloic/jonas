from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from config import settings

MSG_UNAUTHORIZED = "Unauthorized"
MSG_RECEIVED = "Received"
MSG_PHOTO_RECEIVED = "Photo received."


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return
    # reject all message which are not from TELEGRAM_ALLOWED_CHAT_ID
    if str(chat.id) != settings.telegram_allowed_chat_id:
        await message.reply_text(MSG_UNAUTHORIZED)
        return

    # Route to dispatcher
    # from api.agent.dispatcher import dispatch
    # await dispatch(update, context)
    await message.reply_text(MSG_RECEIVED)

    if message.photo:
        file_id = message.photo[-1].file_id
        file = await context.bot.get_file(file_id)
        await file.download_to_drive(f"/var/jonas/media/{file_id}.jpg")


def build_app():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    return app
