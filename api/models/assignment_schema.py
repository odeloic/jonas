from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SectionType(StrEnum):
    REORDER = "REORDER"
    COMPLETION = "COMPLETION"
    FILL_IN_THE_BLANK = "FILL_IN_THE_BLANK"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"


def _indices_contiguous(items: list, *, label: str) -> None:
    """Raise ValueError unless [item.index for item in items] == [0..N-1]."""
    expected = list(range(len(items)))
    actual = [it.index for it in items]
    if actual != expected:
        raise ValueError(
            f"{label} indices must be a contiguous 0-based range matching list order. "
            f"Got {actual}, expected {expected}."
        )


class Blank(BaseModel):
    """One blank in a criterion-graded item. Judge sees one Blank per call."""

    index: int
    grading_criterion: str
    example_answer: str
    is_sentence_initial: bool

    @field_validator("grading_criterion", "example_answer")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class Option(BaseModel):
    """One choice in a closed item (MULTIPLE_CHOICE)."""

    index: int
    text: str
    is_correct: bool

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Option.text must be non-empty")
        return v


class ReorderToken(BaseModel):
    """One token in REORDER. List order is the correct order; `index` matches list position."""

    index: int
    text: str

    @field_validator("text")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ReorderToken.text must be non-empty")
        return v


class ReorderItem(BaseModel):
    type: Literal[SectionType.REORDER]
    tokens: list[ReorderToken]
    hint: str | None = None

    @model_validator(mode="after")
    def _validate_tokens(self) -> ReorderItem:
        if not self.tokens:
            raise ValueError("REORDER item must have at least one token")
        _indices_contiguous(self.tokens, label="REORDER tokens")
        return self


class MultipleChoiceItem(BaseModel):
    type: Literal[SectionType.MULTIPLE_CHOICE]
    question: str
    options: list[Option]
    hint: str | None = None

    @model_validator(mode="after")
    def _validate_options(self) -> MultipleChoiceItem:
        if len(self.options) < 2:
            raise ValueError("MULTIPLE_CHOICE must have at least 2 options")
        _indices_contiguous(self.options, label="MULTIPLE_CHOICE options")
        correct = [opt for opt in self.options if opt.is_correct]
        if len(correct) != 1:
            raise ValueError(
                f"MULTIPLE_CHOICE must have exactly one is_correct=True option, got {len(correct)}"
            )
        return self


class CriterionItem(BaseModel):
    """Used for COMPLETION and FILL_IN_THE_BLANK.

    The question contains no blank markers; `blanks` describes how many answers are
    expected and how each is graded. The judge sees one Blank per call.
    """

    type: Literal[SectionType.COMPLETION, SectionType.FILL_IN_THE_BLANK]
    question: str
    blanks: list[Blank]
    hint: str | None = None

    @model_validator(mode="after")
    def _validate_blanks(self) -> CriterionItem:
        if not self.blanks:
            raise ValueError(f"{self.type} item must have at least one blank")
        _indices_contiguous(self.blanks, label=f"{self.type} blanks")
        return self


AssignmentItem = Annotated[
    ReorderItem | MultipleChoiceItem | CriterionItem,
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


class BlankFeedback(BaseModel):
    """Per-blank verdict for criterion-graded items. None of these fields apply
    to closed types — they leave ItemFeedback.blank_feedbacks as None."""

    index: int
    correct: bool
    rationale: str
    example_answer: str | None = None
    grading_criterion: str | None = None


class ItemFeedback(BaseModel):
    correct: bool
    user_answer: list[str]
    correct_answer: str | None = None
    example_answer: str | None = None
    grading_criterion: str | None = None
    hint: str | None = None
    blank_feedbacks: list[BlankFeedback] | None = None


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
