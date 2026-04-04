import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    MessageReactionHandler,
    filters,
)

from config import settings
from db import async_session
from models.assignment import Assignment
from models.learner_profile import LearnerProfile
from models.submission import AssignmentSubmission
from models.triage import ImageCategory
from services.assignment import generate_assignment, save_assignment
from services.content_extraction import extract_page
from services.ingestion import check_processed_images, persist_extractions
from services.vision_triage import download_photos_as_base64, triage_images

log = structlog.get_logger()

WAITING_FOR_PHOTOS = 0
KEY_PHOTO_FILE_IDS = "photo_file_ids"
KEY_PHOTO_UNIQUE_IDS = "photo_unique_ids"


def _msg_start_first() -> str:
    cmd = settings.telegram_start_command
    return f"Bitte starte zuerst mit /{cmd}, damit ich dich kennenlernen kann."


def _clear_photo_data(user_data: dict) -> None:
    user_data.pop(KEY_PHOTO_FILE_IDS, None)
    user_data.pop(KEY_PHOTO_UNIQUE_IDS, None)


async def _has_profile(chat_id: int | str) -> bool:
    async with async_session() as session:
        result = await session.scalar(
            select(LearnerProfile.id).where(LearnerProfile.telegram_chat_id == str(chat_id))
        )
        return result is not None


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return

    chat_id = str(chat.id)
    async with async_session() as session:
        existing = await session.scalar(
            select(LearnerProfile.id).where(LearnerProfile.telegram_chat_id == chat_id)
        )

    teach = settings.telegram_teach_command
    if existing:
        await message.reply_text(
            "Willkommen zurück! Du bist bereits registriert.\n\n"
            f"Schicke mir Fotos aus deinem Lehrbuch mit /{teach} —\n"
            "ich erstelle daraus Übungen für dich."
        )
        return

    async with async_session() as session:
        async with session.begin():
            profile = LearnerProfile(telegram_chat_id=chat_id)
            session.add(profile)

    log.info("learner_profile_created", chat_id=chat_id)
    await message.reply_text(
        "Hallo! Ich bin Jonas, dein Deutsch-Tutor.\n\n"
        "So funktioniert's:\n"
        f"1. Schicke mir Fotos aus deinem Lehrbuch mit /{teach}\n"
        "2. Ich lese den Inhalt und erstelle eine Übung\n"
        "3. Du bearbeitest die Übung und bekommst Feedback\n\n"
        f"Lass uns loslegen! Schicke /{teach}, um zu beginnen."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    if chat is None or message is None:
        return

    if not await _has_profile(chat.id):
        await message.reply_text(_msg_start_first())
        return

    log.info("message_received", chat_id=chat.id, text=message.text)


async def start_generate_assignment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert context.user_data is not None
    message = update.effective_message
    if message is None:
        return ConversationHandler.END

    chat = update.effective_chat
    if chat is None or not await _has_profile(chat.id):
        if message:
            await message.reply_text(_msg_start_first())
        return ConversationHandler.END

    log.info("teach_started", chat_id=chat.id)

    context.user_data[KEY_PHOTO_FILE_IDS] = []
    context.user_data[KEY_PHOTO_UNIQUE_IDS] = []
    await message.reply_text(
        'Schicke mir deine Fotos! Wenn du fertig bist, schreib einfach "fertig" oder "done".'
    )

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

    teach = settings.telegram_teach_command
    if not file_ids:
        await message.reply_text(
            f"Du hast keine Fotos geschickt. Bitte starte mit /{teach} erneut."
        )
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
            f"Versuche es mit Buchseiten oder Grammatik-Screenshots (/{teach})."
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
        assignment = await save_assignment(
            topic, assignment_content, rule_ids, telegram_chat_id=str(chat.id)
        )

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


_DONE_PATTERN = r"^\s*(done|fertig|ok|k|klar|finished|complete|let'?s\s+go)\s*$"

_DONE_FILTER = filters.Regex(_DONE_PATTERN) & filters.TEXT


def _queue_to_langfuse_dataset(submission: AssignmentSubmission) -> None:
    """Add a flagged submission's trace to the grading-feedback dataset in Langfuse."""
    if not settings.langfuse_enabled or not settings.langfuse_public_key:
        return
    from langfuse import Langfuse  # noqa: PLC0415

    lf = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    lf.create_dataset_item(
        dataset_name="grading-feedback",
        input={"submission_id": submission.id, "langfuse_trace_id": submission.langfuse_trace_id},
        expected_output=None,
        metadata={
            "submission_id": submission.id,
            "flagged_at": submission.flagged_at.isoformat() if submission.flagged_at else None,
        },
    )
    lf.flush()


async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Telegram message reactions — 👎 flags the submission for review."""
    reaction = update.message_reaction
    if reaction is None:
        return
    if not await _has_profile(reaction.chat.id):
        return

    thumbs_down = any(
        getattr(r, "emoji", None) == "\U0001f44e" for r in (reaction.new_reaction or [])
    )
    if not thumbs_down:
        return

    message_id = str(reaction.message_id)
    async with async_session() as session:
        async with session.begin():
            stmt = select(AssignmentSubmission).where(
                AssignmentSubmission.telegram_message_id == message_id
            )
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()

            if submission is None:
                log.info("reaction_no_submission_found", message_id=message_id)
                return

            submission.flagged_for_review = True
            submission.flagged_at = datetime.now(UTC)

    if submission.langfuse_trace_id:
        _queue_to_langfuse_dataset(submission)

    await context.bot.send_message(
        chat_id=reaction.chat.id,
        text="Notiert. Ich lerne daraus.",
    )
    log.info("submission_flagged", submission_id=submission.id)


def build_app():
    app = ApplicationBuilder().token(settings.telegram_bot_token).updater(None).build()

    teach_conv = ConversationHandler(
        entry_points=[
            CommandHandler(settings.telegram_teach_command, start_generate_assignment),
        ],
        states={
            WAITING_FOR_PHOTOS: [
                MessageHandler(filters.PHOTO, collect_photo),
                MessageHandler(_DONE_FILTER, finish_teach),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout_teach),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_teach)],
        conversation_timeout=300,
    )

    app.add_handler(CommandHandler(settings.telegram_start_command, handle_start))
    app.add_handler(teach_conv)
    app.add_handler(MessageReactionHandler(handle_reaction))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    return app
