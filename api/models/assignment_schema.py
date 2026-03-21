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
