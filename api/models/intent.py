from enum import StrEnum

from pydantic import BaseModel


class Intent(StrEnum):
    PRACTICE = "PRACTICE"
    QUESTION = "QUESTION"
    IGNORE = "IGNORE"


class IntentResult(BaseModel):
    intent: Intent
    confidence: float
