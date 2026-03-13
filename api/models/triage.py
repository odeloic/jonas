from enum import StrEnum

from pydantic import BaseModel


class ImageCategory(StrEnum):
    BOOK_PAGE = "BOOK_PAGE"
    GRAMMAR_SCREENSHOT = "GRAMMAR_SCREENSHOT"
    OTHER = "OTHER"


class ImageClassification(BaseModel):
    index: int
    category: ImageCategory


class TriageResponse(BaseModel):
    classifications: list[ImageClassification]


class TriageResult(BaseModel):
    """Enriched with file_id after the LLM call."""

    file_id: str
    category: ImageCategory
