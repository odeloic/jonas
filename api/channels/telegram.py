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
from models.triage import ImageCategory
from services.content_extraction import extract_page
from services.vision_triage import download_photos_as_base64, triage_images

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
    await message.reply_text(f"Danke! {len(file_ids)} Foto(s) empfangen. Wird geprüft....")
    try:
        base64_images = await download_photos_as_base64(context.bot, file_ids)
        triage_results = await triage_images(base64_images)
    except Exception:
        log.exception("teach_triage_failed")
        await message.reply_text(
            "Beim prüfen der Fotos ist ein Fehler aufgetreten. Bitte versuche es später erneut."
        )
        context.user_data.pop(KEY_PHOTO_FILE_IDS, None)
        return ConversationHandler.END

    valid = [r for r in triage_results if r.category != ImageCategory.OTHER]
    rejected = [r for r in triage_results if r.category == ImageCategory.OTHER]

    if rejected:
        log.info("teach_images_rejected", count=len(rejected))
        await message.reply_text(
            f"{len(rejected)} Foto(s) sind kein Lernmaterial und wurden aussortiert."
        )

    if not valid:
        log.info("teach_all_rejected")
        await message.reply_text(
            "Keines der Fotos enthält deutsches Lernmaterial. "
            "Bitte versuche es mit Buchseiten oder Grammatik-Screenshots erneut (/teach)."
        )
        context.user_data.pop(KEY_PHOTO_FILE_IDS, None)
        return ConversationHandler.END

    log.info("teach_triage_passed", valid=len(valid), categories=[r.category for r in valid])

    await message.reply_text(
        f"Danke! {len(valid)} Foto(s) erkannt als Lernmaterial. Verarbeitung startet..."
    )

    # Extracting content from each valid image
    valid_b64 = {fid: b64 for fid, b64 in base64_images}
    extractions = []
    for r in valid:
        try:
            extraction = await extract_page(valid_b64[r.file_id])
            extractions.append(extraction)
            log.info("teach_extraction_ok", file_id=r.file_id, topic=extraction.topic)
        except Exception:
            log.exception("teach_extraction_failed", file_id=r.file_id)
            await message.reply_text(
                "Ein foto konnte nicht verabeitet werden und wurde überspungen."
            )  # TODO: should delete images / discarded
    if extractions:
        # Summarize findings
        total_rules = sum(len(e.grammar_rules) for e in extractions)
        total_vocab = sum(len(e.vocabulary) for e in extractions)
        await message.reply_text(
            f"Fertig! {total_rules} Grammatikregel(n) und {total_vocab} Vokabeln extrahiert"
        )
        # TODO: NEXT up Persist extractions to Postgres + Qdrant
    else:
        await message.reply_text("Aus den Fotos konnte leider kein Inhalt extrahiert werden.")

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
    app = ApplicationBuilder().token(settings.telegram_bot_token).updater(None).build()

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
