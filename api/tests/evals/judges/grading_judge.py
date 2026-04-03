"""LLM-as-judge for semantic grading evaluation.

All judge calls use trace_name='semantic_grading' so they are visible in
Langfuse under the reserved trace group that ODE-245 will query.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from services.llm_service import LLMResult, LLMService

_JUDGE_SYSTEM_PROMPT = """\
Du bist ein Experte für die deutsche Sprache.
Bewertet die Schülerantwort anhand der Musterantwort.
Gib eine Punktzahl von 0.0 (völlig falsch) bis 1.0 (vollständig korrekt) zurück
und begründe deine Bewertung kurz auf Deutsch.
"""


class _JudgeResponse(BaseModel):
    score: float
    rationale: str


@dataclass
class JudgeResult:
    score: float
    rationale: str
    raw_result: LLMResult


async def judge_answer(
    *,
    student_answer: str,
    correct_answer: str,
    question: str,
    llm: LLMService,
) -> JudgeResult:
    """Grade a student answer against the correct answer using an LLM judge.

    Always traces as 'semantic_grading' — the reserved trace name for ODE-245.
    """
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Frage: {question}\n"
                f"Musterantwort: {correct_answer}\n"
                f"Schülerantwort: {student_answer}"
            ),
        },
    ]
    result = await llm.complete_structured(
        messages=messages,
        response_format=_JudgeResponse,
        trace_name="semantic_grading",
    )
    return JudgeResult(
        score=result.parsed.score,
        rationale=result.parsed.rationale,
        raw_result=result,
    )
