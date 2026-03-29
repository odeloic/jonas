from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from db import async_session
from models.grammar_rule import GrammarRule

router = APIRouter(prefix="/api/grammar", tags=["grammar"])
log = structlog.get_logger()


class GrammarRuleOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    topic: str
    rule_name: str
    explanation: str
    pattern: str | None
    examples: list[str]
    verified: bool
    created_at: datetime


class TopicSummary(BaseModel):
    topic: str
    count: int


@router.get("", response_model=list[GrammarRuleOut])
async def list_grammar_rules(topic: str | None = None, q: str | None = None):
    async with async_session() as session:
        stmt = select(GrammarRule).order_by(GrammarRule.topic, GrammarRule.rule_name)
        if topic:
            stmt = stmt.where(GrammarRule.topic == topic)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                GrammarRule.rule_name.ilike(pattern)
                | GrammarRule.explanation.ilike(pattern)
                | GrammarRule.topic.ilike(pattern)
            )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    log.info("grammar_listed", count=len(rows))
    return rows


@router.get("/topics", response_model=list[TopicSummary])
async def list_topics():
    async with async_session() as session:
        stmt = (
            select(GrammarRule.topic, func.count(GrammarRule.id).label("count"))
            .group_by(GrammarRule.topic)
            .order_by(GrammarRule.topic)
        )
        result = await session.execute(stmt)
        rows = result.all()
    return [TopicSummary(topic=r.topic, count=r.count) for r in rows]


@router.get("/{rule_id}", response_model=GrammarRuleOut)
async def get_grammar_rule(rule_id: int):
    async with async_session() as session:
        row = await session.get(GrammarRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Grammar rule not found")
    return row
