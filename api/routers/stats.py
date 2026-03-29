import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import distinct, func, select

from db import async_session
from models.assignment import Assignment
from models.grammar_rule import GrammarRule
from models.vocabulary_item import VocabularyItem

router = APIRouter(prefix="/api/stats", tags=["stats"])
log = structlog.get_logger()


class StatsOut(BaseModel):
    grammar_rules: int
    vocabulary_items: int
    assignments: int
    topics: int


@router.get("", response_model=StatsOut)
async def get_stats():
    async with async_session() as session:
        grammar_count = await session.scalar(select(func.count(GrammarRule.id)))
        vocab_count = await session.scalar(select(func.count(VocabularyItem.id)))
        assignment_count = await session.scalar(select(func.count(Assignment.id)))
        topic_count = await session.scalar(select(func.count(distinct(GrammarRule.topic))))
    return StatsOut(
        grammar_rules=grammar_count or 0,
        vocabulary_items=vocab_count or 0,
        assignments=assignment_count or 0,
        topics=topic_count or 0,
    )
