from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from db import async_session
from models.flashcard_set import FlashcardSet
from models.vocabulary_item import VocabularyItem

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])
log = structlog.get_logger()


# --- Response models ---


class FlashcardItem(BaseModel):
    id: int
    word: str
    article: str | None
    plural: str | None
    word_class: str
    definition_de: str | None
    definition_en: str | None
    example_sentence: str | None


class FlashcardSetSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    telegram_chat_id: str
    sent_at: datetime | None
    created_at: datetime


class FlashcardSetDetail(BaseModel):
    id: int
    telegram_chat_id: str
    items: list[FlashcardItem]
    sent_at: datetime | None
    created_at: datetime


# --- Endpoints ---


@router.get("", response_model=list[FlashcardSetSummary])
async def list_flashcard_sets():
    async with async_session() as session:
        stmt = select(FlashcardSet).order_by(FlashcardSet.created_at.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
    log.info("flashcard_sets_listed", count=len(rows))
    return rows


@router.get("/{set_id}", response_model=FlashcardSetDetail)
async def get_flashcard_set(set_id: int):
    async with async_session() as session:
        fset = await session.get(FlashcardSet, set_id)
    if not fset:
        raise HTTPException(status_code=404, detail="Flashcard set not found")

    # Fetch vocabulary items by IDs
    async with async_session() as session:
        stmt = select(VocabularyItem).where(VocabularyItem.id.in_(fset.vocabulary_item_ids))
        result = await session.execute(stmt)
        vocab_rows = result.scalars().all()

    items = [
        FlashcardItem(
            id=v.id,
            word=v.word,
            article=v.article,
            plural=v.plural,
            word_class=v.word_class,
            definition_de=v.definition_de,
            definition_en=v.definition_en,
            example_sentence=v.example_sentence,
        )
        for v in vocab_rows
    ]

    log.info("flashcard_set_fetched", set_id=set_id, item_count=len(items))
    return FlashcardSetDetail(
        id=fset.id,
        telegram_chat_id=fset.telegram_chat_id,
        items=items,
        sent_at=fset.sent_at,
        created_at=fset.created_at,
    )
