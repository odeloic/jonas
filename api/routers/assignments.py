from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from db import async_session
from models.assignment import Assignment
from models.assignment_schema import AssignmentContent

router = APIRouter(prefix="/api/assignments", tags=["assignments"])
log = structlog.get_logger()


class AssignmentSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    type: str
    topic: str
    source: str
    sent_at: datetime | None
    created_at: datetime


class AssignmentDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    type: str
    topic: str
    content: AssignmentContent
    grammar_rule_ids: list[int]
    source: str
    sent_at: datetime | None
    created_at: datetime


@router.get("", response_model=list[AssignmentSummary])
async def list_assignments():
    async with async_session() as session:
        stmt = select(Assignment).order_by(Assignment.created_at.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
    log.info("assignments_listed", count=len(rows))
    return rows


@router.get("/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(assignment_id: int):
    async with async_session() as session:
        row = await session.get(Assignment, assignment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    log.info("assignment_fetched", assignment_id=assignment_id)
    return row
