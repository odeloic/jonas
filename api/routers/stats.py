from datetime import date

import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import distinct, func, select

from db import async_session
from models.assignment import Assignment
from models.grammar_rule import GrammarRule
from models.learner_profile import LearnerProfile
from models.vocabulary_item import VocabularyItem

router = APIRouter(prefix="/api/stats", tags=["stats"])
log = structlog.get_logger()


class ProfileOut(BaseModel):
    streak_days: int = 0
    xp: int = 0
    cefr_estimate: str = "B1"
    weak_topics: dict = {}
    last_active_date: date | None = None


class StatsOut(BaseModel):
    grammar_rules: int
    vocabulary_items: int
    assignments: int
    topics: int
    profile: ProfileOut | None = None


@router.get("", response_model=StatsOut)
async def get_stats():
    async with async_session() as session:
        grammar_count = await session.scalar(select(func.count(GrammarRule.id)))
        vocab_count = await session.scalar(select(func.count(VocabularyItem.id)))
        assignment_count = await session.scalar(select(func.count(Assignment.id)))
        topic_count = await session.scalar(select(func.count(distinct(GrammarRule.topic))))

        profile = None
        row = await session.scalar(
            select(LearnerProfile).order_by(LearnerProfile.updated_at.desc()).limit(1)
        )
        if row:
            profile = ProfileOut(
                streak_days=row.streak_days,
                xp=row.xp,
                cefr_estimate=row.cefr_estimate,
                weak_topics=row.weak_topics,
                last_active_date=row.last_active_date,
            )

    return StatsOut(
        grammar_rules=grammar_count or 0,
        vocabulary_items=vocab_count or 0,
        assignments=assignment_count or 0,
        topics=topic_count or 0,
        profile=profile,
    )
