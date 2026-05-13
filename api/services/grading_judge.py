"""LLM-as-judge for criterion-based grading of open-ended exercise items.

The judge evaluates whether a student's submission satisfies a free-text
`grading_criterion` that describes the linguistic rule under test. The
`example_answer` is informational only — it is shown to the judge as an
illustration but is *not* the answer being matched. Multiple valid completions
that all satisfy the criterion must all grade correct.

All judge calls use trace_name='semantic_grading' so they aggregate in Langfuse
under the reserved trace group queried by the grading-eval dashboard.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from services.llm_service import LLMResult, LLMService

_JUDGE_SYSTEM_PROMPT = """\
Du bist ein Experte für die deutsche Sprache und bewertest Schülerantworten zu \
Lückenübungen.

Du erhältst:
- die Aufgabenfrage (Satz mit einer oder mehreren Lücken, markiert durch ___),
- ein grading_criterion (Naturalsprachliche Beschreibung der Regel, die getestet wird, \
  und was eine korrekte Antwort ausmacht),
- ein example_answer (EINE mögliche Musterantwort — KEINE Ankerlösung. \
  Andere Antworten, die das Kriterium erfüllen, sind ebenso korrekt.),
- die Schülerantworten als Liste in der Reihenfolge der Lücken.

Bewerte ausschließlich danach, ob die Schülerantworten das grading_criterion erfüllen. \
Lexikalische Abweichungen zur example_answer sind erlaubt, solange das Kriterium erfüllt ist \
(z. B. "meiner Freundin" statt "meiner Schwester" für eine feminine Genitiv-Nominalphrase).

Wenn das Kriterium mehrere Lücken beschreibt, muss JEDE Lücke das Kriterium erfüllen, \
damit is_correct=true zurückgegeben wird. Eine Lücke falsch → is_correct=false.

Gib zusätzlich eine Punktzahl von 0.0 (völlig falsch) bis 1.0 (vollständig korrekt) \
und eine kurze Begründung auf Deutsch zurück.
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
    question: str,
    grading_criterion: str,
    example_answer: str,
    student_answers: list[str],
    llm: LLMService,
) -> JudgeResult:
    """Grade student answers against a criterion using an LLM judge.

    Always traces as 'semantic_grading' — the reserved trace name for the
    grading-eval dashboard.
    """
    rendered_answers = "\n".join(f"  [{i + 1}] {ans}" for i, ans in enumerate(student_answers))
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Frage: {question}\n"
                f"Kriterium: {grading_criterion}\n"
                f"Beispielantwort: {example_answer}\n"
                f"Schülerantworten (in Lücken-Reihenfolge):\n{rendered_answers}"
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
