from datetime import datetime

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import distinct, select

from db import async_session
from models.vocabulary_item import VocabularyItem

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])
log = structlog.get_logger()


class VocabItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    word: str
    article: str | None
    plural: str | None
    word_class: str
    definition_de: str | None
    definition_en: str | None
    example_sentence: str | None
    created_at: datetime


@router.get("", response_model=list[VocabItemOut])
async def list_vocabulary(q: str | None = None, word_class: str | None = None):
    async with async_session() as session:
        stmt = select(VocabularyItem).order_by(VocabularyItem.word)
        if word_class:
            stmt = stmt.where(VocabularyItem.word_class == word_class)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                VocabularyItem.word.ilike(pattern)
                | VocabularyItem.definition_en.ilike(pattern)
                | VocabularyItem.definition_de.ilike(pattern)
            )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    log.info("vocabulary_listed", count=len(rows))
    return rows


@router.get("/word-classes", response_model=list[str])
async def list_word_classes():
    async with async_session() as session:
        stmt = select(distinct(VocabularyItem.word_class)).order_by(VocabularyItem.word_class)
        result = await session.execute(stmt)
        return result.scalars().all()
