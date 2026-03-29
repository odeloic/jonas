from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class SectionType(StrEnum):
    REORDER = "REORDER"
    COMPLETION = "COMPLETION"
    ADJEKTIV_DEKLINATION = "ADJEKTIV_DEKLINATION"
    FILL_IN_THE_BLANK = "FILL_IN_THE_BLANK"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


class AssignmentItem(BaseModel):
    question: str
    correct_answer: str
    options: list[str] | None = None
    hint: str | None = None


class AssignmentSection(BaseModel):
    type: SectionType
    title: str
    instructions: str
    items: list[AssignmentItem]


class AssignmentContent(BaseModel):
    """Full assignment structure"""

    sections: list[AssignmentSection]


# --- Submission schemas ---


class SectionAnswers(BaseModel):
    items: list[str]


class SubmissionAnswers(BaseModel):
    sections: list[SectionAnswers]


class ItemFeedback(BaseModel):
    correct: bool
    user_answer: str
    correct_answer: str
    hint: str | None = None


class SectionFeedback(BaseModel):
    items: list[ItemFeedback]


class SubmissionFeedback(BaseModel):
    sections: list[SectionFeedback]


class SubmissionResult(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    assignment_id: int
    score: int
    max_score: int
    feedback: SubmissionFeedback
    submitted_at: datetime
