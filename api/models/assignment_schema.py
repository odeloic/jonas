from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class SectionType(StrEnum):
    REORDER = "REORDER"
    COMPLETION = "COMPLETION"
    ADJEKTIV_DEKLINATION = "ADJEKTIV_DEKLINATION"
    FILL_IN_THE_BLANK = "FILL_IN_THE_BLANK"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


class ReorderItem(BaseModel):
    type: Literal[SectionType.REORDER]
    correct_tokens: list[str]
    hint: str | None = None


class MultipleChoiceItem(BaseModel):
    type: Literal[SectionType.MULTIPLE_CHOICE]
    question: str
    options: list[str]
    correct_answer: str
    hint: str | None = None


class AdjektivDeklinationItem(BaseModel):
    type: Literal[SectionType.ADJEKTIV_DEKLINATION]
    question: str
    correct_ending: str
    candidate_endings: list[str]
    hint: str | None = None


class CriterionItem(BaseModel):
    """Used for COMPLETION and FILL_IN_THE_BLANK.

    The judge grades a student's submission against `grading_criterion`. The
    `example_answer` is shown back to the student on a wrong verdict but is not
    consulted by the judge for grading.
    """

    type: Literal[SectionType.COMPLETION, SectionType.FILL_IN_THE_BLANK]
    question: str
    grading_criterion: str
    example_answer: str
    hint: str | None = None


AssignmentItem = Annotated[
    ReorderItem | MultipleChoiceItem | AdjektivDeklinationItem | CriterionItem,
    Field(discriminator="type"),
]


class AssignmentSection(BaseModel):
    type: SectionType
    title: str
    instructions: str
    items: list[AssignmentItem]

    @model_validator(mode="after")
    def _items_match_section_type(self) -> AssignmentSection:
        for i, item in enumerate(self.items):
            if item.type != self.type:
                raise ValueError(
                    f"items[{i}].type={item.type!r} does not match section.type={self.type!r}"
                )
        return self


class AssignmentContent(BaseModel):
    sections: list[AssignmentSection]


# --- Submission schemas ---


class SectionAnswers(BaseModel):
    items: list[list[str]]


class SubmissionAnswers(BaseModel):
    sections: list[SectionAnswers]


class ItemFeedback(BaseModel):
    correct: bool
    user_answer: list[str]
    correct_answer: str | None = None
    example_answer: str | None = None
    grading_criterion: str | None = None
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
