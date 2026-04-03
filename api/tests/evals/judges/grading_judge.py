"""LLM-as-judge for semantic grading evaluation.

All judge calls use trace_name='semantic_grading' so they are visible in
Langfuse under the reserved trace group that ODE-245 will query.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from services.llm_service import LLMResult, LLMService

_JUDGE_SYSTEM_PROMPT = """\
Du bist ein Experte für die deutsche Sprache und bewertest Schülerantworten.

Entscheide, ob die Schülerantwort inhaltlich korrekt ist (is_correct: true oder false).
Semantisch gleichwertige Antworten gelten als korrekt — zum Beispiel gültige V2-Umstellungen
oder Perfekt statt Präteritum in gesprochen-deutschem Kontext.

Wichtig bei Konnektoren: Koordinierende Konjunktionen (denn, aber, oder, und, sondern) und
subordinierende Konjunktionen (weil, da, obwohl, wenn, dass …) sind NICHT austauschbar,
auch wenn sie inhaltlich ähnlich sind. Sie verlangen unterschiedliche Wortstellungen.
Wenn die Satzstruktur in der Frage bereits eine bestimmte Wortstellung vorgibt (z. B.
Verbendstellung im Nebensatz), ist nur der passende Konjunktionstyp korrekt.

Gib außerdem eine Punktzahl von 0.0 (völlig falsch) bis 1.0 (vollständig korrekt)
und eine kurze Begründung auf Deutsch.
"""


class _JudgeResponse(BaseModel):
    is_correct: bool
    score: float
    rationale: str


@dataclass
class JudgeResult:
    is_correct: bool
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
        is_correct=result.parsed.is_correct,
        score=result.parsed.score,
        rationale=result.parsed.rationale,
        raw_result=result,
    )
