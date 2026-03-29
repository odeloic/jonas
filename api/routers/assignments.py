import asyncio
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from config import settings
from db import async_session
from models.assignment import Assignment
from models.assignment_schema import (
    AssignmentContent,
    SubmissionAnswers,
    SubmissionFeedback,
    SubmissionResult,
)
from models.submission import AssignmentSubmission
from services.scoring import score_submission

router = APIRouter(prefix="/api/assignments", tags=["assignments"])
log = structlog.get_logger()


# --- Response models ---


class AssignmentSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    type: str
    topic: str
    source: str
    sent_at: datetime | None
    created_at: datetime


class ExerciseItem(BaseModel):
    question: str
    options: list[str] | None = None


class ExerciseSection(BaseModel):
    type: str
    title: str
    instructions: str
    items: list[ExerciseItem]


class ExerciseContent(BaseModel):
    sections: list[ExerciseSection]


class AssignmentExercise(BaseModel):
    id: int
    type: str
    topic: str
    content: ExerciseContent
    source: str
    created_at: datetime


class SubmitRequest(BaseModel):
    answers: SubmissionAnswers


# --- Endpoints ---


@router.get("", response_model=list[AssignmentSummary])
async def list_assignments():
    async with async_session() as session:
        stmt = select(Assignment).order_by(Assignment.created_at.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
    log.info("assignments_listed", count=len(rows))
    return rows


@router.get("/{assignment_id}", response_model=AssignmentExercise)
async def get_assignment(assignment_id: int):
    async with async_session() as session:
        row = await session.get(Assignment, assignment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")

    full_content = AssignmentContent.model_validate(row.content)
    exercise_content = ExerciseContent(
        sections=[
            ExerciseSection(
                type=s.type,
                title=s.title,
                instructions=s.instructions,
                items=[
                    ExerciseItem(question=item.question, options=item.options) for item in s.items
                ],
            )
            for s in full_content.sections
        ]
    )

    log.info("assignment_fetched", assignment_id=assignment_id)
    return AssignmentExercise(
        id=row.id,
        type=row.type,
        topic=row.topic,
        content=exercise_content,
        source=row.source,
        created_at=row.created_at,
    )


@router.post("/{assignment_id}/submit", response_model=SubmissionResult)
async def submit_assignment(assignment_id: int, body: SubmitRequest, request: Request):
    async with async_session() as session:
        assignment = await session.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    content = AssignmentContent.model_validate(assignment.content)

    if len(body.answers.sections) != len(content.sections):
        raise HTTPException(status_code=422, detail="Section count mismatch")
    for i, (section, answers) in enumerate(
        zip(content.sections, body.answers.sections, strict=True)
    ):
        if len(answers.items) != len(section.items):
            raise HTTPException(status_code=422, detail=f"Item count mismatch in section {i}")

    score, max_score, feedback = score_submission(content, body.answers)

    async with async_session() as session:
        async with session.begin():
            submission = AssignmentSubmission(
                assignment_id=assignment_id,
                answers=body.answers.model_dump(),
                score=score,
                max_score=max_score,
                feedback=feedback.model_dump(),
            )
            session.add(submission)
            await session.flush()
            submission_id = submission.id

    log.info(
        "submission_created",
        submission_id=submission_id,
        score=score,
        max_score=max_score,
    )

    # ODE-258: push results to Telegram
    tg_app = getattr(request.app.state, "tg_app", None)
    if tg_app and settings.telegram_allowed_chat_id:
        error_count = max_score - score
        tg_text = (
            f"Übung #{assignment_id} abgegeben!\n\n"
            f"Ergebnis: {score}/{max_score} richtig\n"
            f"Fehler: {error_count}"
        )
        if settings.web_base_url:
            results_url = (
                f"{settings.web_base_url}/assignments/{assignment_id}/results/{submission_id}"
            )
            tg_text += f"\n\nDetails: {results_url}"

        asyncio.create_task(
            tg_app.bot.send_message(
                chat_id=settings.telegram_allowed_chat_id,
                text=tg_text,
            )
        )

    return SubmissionResult(
        id=submission_id,
        assignment_id=assignment_id,
        score=score,
        max_score=max_score,
        feedback=feedback,
        submitted_at=submission.submitted_at,
    )


@router.get("/{assignment_id}/results/{submission_id}", response_model=SubmissionResult)
async def get_submission(assignment_id: int, submission_id: int):
    async with async_session() as session:
        submission = await session.get(AssignmentSubmission, submission_id)
    if not submission or submission.assignment_id != assignment_id:
        raise HTTPException(status_code=404, detail="Submission not found")

    return SubmissionResult(
        id=submission.id,
        assignment_id=submission.assignment_id,
        score=submission.score,
        max_score=submission.max_score,
        feedback=SubmissionFeedback.model_validate(submission.feedback),
        submitted_at=submission.submitted_at,
    )
