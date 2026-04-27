from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel
from sqlalchemy import func, select

from config import settings
from db import async_session
from models.extraction import VocabularyItem as VocabularyItemSchema
from models.flashcard_log import FlashcardLog
from models.flashcard_set import FlashcardSet
from models.learner_profile import LearnerProfile
from models.source import Source
from models.vocabulary_item import VocabularyItem
from services.llm_service import LLMService

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

log = structlog.get_logger()
_llm = LLMService()

FLASHCARD_SYSTEM_PROMPT = """\
Du bist ein Deutschlehrer. Erstelle neue deutsche Vokabeln für einen Lerner \
auf dem Niveau {cefr_level}.

Anforderungen:
- Alltagstaugliche, nützliche Wörter
- Verschiedene Wortklassen (Nomen, Verben, Adjektive)
- Bei Nomen: 'word' enthält nur das Lemma im Nominativ Singular ohne Artikel
  (z. B. 'Puppe', nicht 'die Puppe' und nicht 'Puppen').
  Den Artikel separat in 'article' ('der'/'die'/'das'),
  die Pluralform separat in 'plural' (ohne Artikel, z. B. 'Puppen').
- Kurze Definition auf Deutsch und Englisch
- Ein Beispielsatz pro Wort
"""


class GeneratedVocabulary(BaseModel):
    items: list[VocabularyItemSchema]


async def select_flashcard_vocab(chat_id: str, count: int) -> list[VocabularyItem]:
    """Select unseen vocabulary items for a user, avoiding repeats."""
    async with async_session() as session:
        sent_ids = select(FlashcardLog.vocabulary_item_id).where(
            FlashcardLog.telegram_chat_id == chat_id
        )
        stmt = (
            select(VocabularyItem)
            .where(VocabularyItem.id.notin_(sent_ids))
            .order_by(func.random())
            .limit(count)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def generate_new_vocabulary(cefr_level: str, count: int) -> list[VocabularyItem]:
    """Generate new vocabulary via LLM and save to DB."""
    system_prompt = FLASHCARD_SYSTEM_PROMPT.format(cefr_level=cefr_level)
    user_content = f"Erstelle {count} neue Vokabeln für das Niveau {cefr_level}."

    result = (
        await _llm.complete_structured(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=GeneratedVocabulary,
            model=settings.default_model,
            max_tokens=2048,
            trace_name="flashcard_vocab_generation",
        )
    ).parsed

    # Persist to DB
    rows: list[VocabularyItem] = []
    async with async_session() as session:
        async with session.begin():
            source = Source(type="AI_GENERATED", status="complete")
            session.add(source)
            await session.flush()

            for item in result.items:
                row = VocabularyItem(
                    word=item.word,
                    article=item.article,
                    plural=item.plural,
                    word_class=item.word_class,
                    definition_de=item.definition_de,
                    definition_en=item.definition_en,
                    example_sentence=item.example_sentence,
                    source_id=source.id,
                )
                session.add(row)
                rows.append(row)
            await session.flush()

    log.info("flashcard_vocab_generated", count=len(rows), cefr_level=cefr_level)
    return rows


def format_flashcard_message(items: list[VocabularyItem]) -> str:
    """Format vocabulary items as a single Telegram flashcard message."""
    parts = ["\U0001f4da Deine täglichen Vokabeln\n"]

    for i, item in enumerate(items, 1):
        word_display = item.word
        if item.article:
            word_display = f"{item.article} {item.word}"
        if item.plural:
            word_display += f" ({item.plural})"

        lines = [f"{i}. {word_display}  [{item.word_class}]"]
        if item.definition_de:
            lines.append(f"   DE: {item.definition_de}")
        if item.definition_en:
            lines.append(f"   EN: {item.definition_en}")
        if item.example_sentence:
            lines.append(f"   Bsp: {item.example_sentence}")
        parts.append("\n".join(lines))

    parts.append("\nViel Erfolg beim Lernen! \U0001f4aa")
    return "\n\n".join(parts)


async def _log_flashcards_sent(chat_id: str, vocab_ids: list[int]) -> None:
    async with async_session() as session:
        async with session.begin():
            for vid in vocab_ids:
                session.add(FlashcardLog(telegram_chat_id=chat_id, vocabulary_item_id=vid))


async def _save_flashcard_set(chat_id: str, vocab_ids: list[int]) -> FlashcardSet:
    """Persist a flashcard set and return the row."""
    async with async_session() as session:
        async with session.begin():
            fset = FlashcardSet(
                telegram_chat_id=chat_id,
                vocabulary_item_ids=vocab_ids,
            )
            session.add(fset)
            await session.flush()
    return fset


async def send_daily_flashcards(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: send daily flashcards to all registered learners."""
    count = settings.flashcard_daily_count
    log.info("flashcard_cron_started", target_count=count)

    async with async_session() as session:
        result = await session.execute(select(LearnerProfile))
        profiles = result.scalars().all()

    if not profiles:
        log.info("flashcard_cron_no_profiles")
        return

    for profile in profiles:
        chat_id = profile.telegram_chat_id
        try:
            # Select saved vocab first
            items = await select_flashcard_vocab(chat_id, count)

            # Fill remainder with AI-generated vocab
            remaining = count - len(items)
            if remaining > 0:
                new_items = await generate_new_vocabulary(
                    cefr_level=profile.cefr_estimate, count=remaining
                )
                items.extend(new_items)

            if not items:
                log.info("flashcard_cron_no_vocab", chat_id=chat_id)
                continue

            vocab_ids = [item.id for item in items]

            # Save flashcard set for web view
            fset = await _save_flashcard_set(chat_id, vocab_ids)

            # Send link via Telegram
            text = (
                f"\U0001f4da Deine täglichen Vokabeln sind da! "
                f"{len(items)} {'Wort' if len(items) == 1 else 'Wörter'} zum Lernen."
            )
            if settings.web_base_url:
                url = f"{settings.web_base_url}/flashcards/{fset.id}"
                text += f"\n\nHier lernen: {url}"

            await context.bot.send_message(chat_id=chat_id, text=text)

            # Mark set as sent
            async with async_session() as session:
                async with session.begin():
                    row = await session.get(FlashcardSet, fset.id)
                    if row:
                        row.sent_at = datetime.now(UTC)

            # Log individual items for repeat prevention
            await _log_flashcards_sent(chat_id, vocab_ids)
            log.info(
                "flashcard_cron_sent",
                chat_id=chat_id,
                set_id=fset.id,
                total=len(items),
            )
        except Exception:
            log.exception("flashcard_cron_failed", chat_id=chat_id)

    log.info("flashcard_cron_finished", profiles=len(profiles))
