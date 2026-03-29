import asyncio
from datetime import UTC, datetime

import structlog
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings
from db import async_session
from models.assignment import Assignment
from models.triage import ImageCategory
from services.assignment import generate_assignment, save_assignment
from services.content_extraction import extract_page
from services.ingestion import check_processed_images, persist_extractions
from services.vision_triage import download_photos_as_base64, triage_images

MSG_UNAUTHORIZED = "Unauthorized"
MSG_RECEIVED = "Received"

log = structlog.get_logger()

WAITING_FOR_PHOTOS = 0
KEY_PHOTO_FILE_IDS = "photo_file_ids"
KEY_PHOTO_UNIQUE_IDS = "photo_unique_ids"


def _clear_photo_data(user_data: dict) -> None:
    user_data.pop(KEY_PHOTO_FILE_IDS, None)
    user_data.pop(KEY_PHOTO_UNIQUE_IDS, None)


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
    context.user_data[KEY_PHOTO_UNIQUE_IDS] = []
    await message.reply_text("Schicke mir deine Fotos! Wenn du fertig bist, sende /done")

    return WAITING_FOR_PHOTOS


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None or not message.photo:
        return WAITING_FOR_PHOTOS

    file_id = message.photo[-1].file_id
    file_unique_id = message.photo[-1].file_unique_id
    context.user_data[KEY_PHOTO_FILE_IDS].append(file_id)
    context.user_data[KEY_PHOTO_UNIQUE_IDS].append(file_unique_id)

    count = len(context.user_data[KEY_PHOTO_FILE_IDS])
    log.info("teach_photo_received", file_id=file_id, total=count)

    return WAITING_FOR_PHOTOS


async def finish_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END
    file_ids = context.user_data.get(KEY_PHOTO_FILE_IDS, [])
    unique_ids = context.user_data.get(KEY_PHOTO_UNIQUE_IDS, [])

    if not file_ids:
        await message.reply_text("Du hast keine Fotos geschickt. Bitte starte mit /teach erneut.")
        return ConversationHandler.END

    # --- Dedup check: skip already-processed images ---
    already_processed = await check_processed_images(unique_ids)
    new_pairs = [
        (fid, uid)
        for fid, uid in zip(file_ids, unique_ids, strict=True)
        if uid not in already_processed
    ]
    skipped = len(file_ids) - len(new_pairs)

    if not new_pairs:
        log.info("teach_all_duplicates", count=len(file_ids))
        await message.reply_text("Diese Bilder wurden bereits verarbeitet.")
        _clear_photo_data(context.user_data)
        return ConversationHandler.END

    if skipped:
        log.info("teach_duplicates_skipped", skipped=skipped)
        await message.reply_text(f"{skipped} Foto(s) wurden bereits verarbeitet und übersprungen.")

    file_ids = [fid for fid, _ in new_pairs]
    unique_ids = [uid for _, uid in new_pairs]

    # Build mapping from file_id -> file_unique_id for later persistence
    fid_to_uid = dict(zip(file_ids, unique_ids, strict=True))

    chat = update.effective_chat
    assert chat is not None
    n = len(file_ids)
    log.info("teach_finished", file_ids=file_ids, count=n)
    await message.reply_text(
        f"Danke! {n} Foto{'s' if n > 1 else ''} empfangen. Ich schaue sie mir an..."
    )

    # --- Step 1: Triage ---
    await chat.send_action(ChatAction.TYPING)
    try:
        base64_images = await download_photos_as_base64(context.bot, file_ids)
        triage_results = await triage_images(base64_images)
    except Exception:
        log.exception("teach_triage_failed")
        await message.reply_text(
            "Beim Prüfen der Fotos ist ein Fehler aufgetreten. Bitte versuche es später erneut."
        )
        _clear_photo_data(context.user_data)
        return ConversationHandler.END

    valid = [r for r in triage_results if r.category != ImageCategory.OTHER]
    rejected = [r for r in triage_results if r.category == ImageCategory.OTHER]

    if rejected:
        log.info("teach_images_rejected", count=len(rejected))
        await message.reply_text(
            f"{len(rejected)} Foto{'s' if len(rejected) > 1 else ''} "
            "sehen nicht nach Lernmaterial aus — übersprungen."
        )

    if not valid:
        log.info("teach_all_rejected")
        await message.reply_text(
            "Ich konnte leider kein deutsches Lernmaterial erkennen. "
            "Versuche es mit Buchseiten oder Grammatik-Screenshots (/teach)."
        )
        _clear_photo_data(context.user_data)
        return ConversationHandler.END

    log.info("teach_triage_passed", valid=len(valid), categories=[r.category for r in valid])
    await message.reply_text(
        f"{len(valid)} Seite{'n' if len(valid) > 1 else ''} erkannt. Ich lese jetzt den Inhalt..."
    )

    # --- Step 2: Extract content ---
    await chat.send_action(ChatAction.TYPING)
    b64_by_file_id = dict(base64_images)
    tasks = [extract_page(b64_by_file_id[r.file_id]) for r in valid]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    extractions = []
    image_metadata = []
    failed_count = 0
    empty_count = 0
    for r, result in zip(valid, results, strict=True):
        if isinstance(result, Exception):
            failed_count += 1
            log.error("teach_extraction_failed", file_id=r.file_id, error=repr(result))
        elif not result.grammar_rules and not result.vocabulary:
            empty_count += 1
            log.warning("teach_extraction_empty", file_id=r.file_id, topic=result.topic)
        else:
            extractions.append(result)
            image_metadata.append((fid_to_uid[r.file_id], r.file_id))
            log.info("teach_extraction_ok", file_id=r.file_id, topic=result.topic)

    if failed_count or empty_count:
        skipped_msgs = []
        if failed_count:
            skipped_msgs.append(f"{failed_count} fehlgeschlagen")
        if empty_count:
            skipped_msgs.append(f"{empty_count} ohne erkennbaren Inhalt")
        await message.reply_text(f"Übersprungen: {', '.join(skipped_msgs)}.")

    if not extractions:
        await message.reply_text(
            "Aus den Fotos konnte ich leider keinen Inhalt herauslesen. "
            "Vielleicht ein schärferes Bild probieren?"
        )
        _clear_photo_data(context.user_data)
        return ConversationHandler.END

    # --- Step 3: Persist + generate assignment ---
    total_rules = sum(len(e.grammar_rules) for e in extractions)
    total_vocab = sum(len(e.vocabulary) for e in extractions)
    await message.reply_text(
        f"{total_rules} Grammatikregel{'n' if total_rules != 1 else ''}"
        f" und {total_vocab} Vokabeln gefunden. "
        "Ich erstelle jetzt deine Übung..."
    )

    await chat.send_action(ChatAction.TYPING)
    try:
        source, rule_ids = await persist_extractions(extractions, image_metadata=image_metadata)
        topic = extractions[0].topic
        assignment_content = await generate_assignment(extractions, topic=topic)
        assignment = await save_assignment(topic, assignment_content, rule_ids)

        item_count = sum(len(s.items) for s in assignment_content.sections)
        section_count = len(assignment_content.sections)

        text = (
            f"Fertig! Übung #{assignment.id} ist bereit: "
            f"{section_count} Abschnitte mit {item_count} Aufgaben.\n\n"
            f"Thema: {topic}"
        )
        if settings.web_base_url:
            url = f"{settings.web_base_url}/assignments/{assignment.id}"
            text += f"\n\nHier starten: {url}"

        await message.reply_text(text)

        async with async_session() as session:
            async with session.begin():
                row = await session.get(Assignment, assignment.id)
                row.sent_at = datetime.now(UTC)

        log.info("teach_persisted", source_id=source.id, assignment_id=assignment.id)
    except Exception:
        log.exception("teach_persist_failed")
        await message.reply_text(
            "Beim Erstellen der Übung ist leider ein Fehler aufgetreten. Bitte versuche es erneut."
        )

    _clear_photo_data(context.user_data)
    return ConversationHandler.END


async def cancel_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END

    _clear_photo_data(context.user_data)
    log.info("teach_cancelled")

    await message.reply_text("Abgebrochen")
    return ConversationHandler.END


async def timeout_teach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is not None:
        _clear_photo_data(context.user_data)
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
