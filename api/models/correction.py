from pydantic import BaseModel


class CorrectionResult(BaseModel):
    has_error: bool
    corrected: str | None = None
    error_type: str | None = None
    explanation: str
    follow_up: str
