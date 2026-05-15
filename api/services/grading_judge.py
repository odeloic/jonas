"""LLM-as-judge for criterion-based grading of one blank at a time.

Each call grades ONE blank against ONE student answer string. Multi-blank items are
graded by `scoring._score_criterion`, which calls the judge once per blank and
aggregates verdicts.

All judge calls use trace_name='semantic_grading' so they aggregate in Langfuse
under the reserved trace group queried by the grading-eval dashboard.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from models.assignment_schema import Blank
from services.llm_service import LLMResult, LLMService

_JUDGE_SYSTEM_PROMPT = """\
Du bist ein Experte für die deutsche Sprache und bewertest EINE Schülerantwort gegen \
EIN grading_criterion.

Du erhältst:
- die Aufgabenfrage (Kontext),
- ein grading_criterion (Naturalsprachliche Beschreibung der Regel, die getestet wird, \
  und was eine korrekte Antwort ausmacht),
- ein example_answer (EINE mögliche Musterantwort — KEINE Ankerlösung. \
  Andere Antworten, die das Kriterium erfüllen, sind ebenso korrekt.),
- ein Flag is_sentence_initial (true/false) — sagt dir, ob diese Antwort das erste Wort \
  des Zielsatzes ist,
- die Schülerantwort als Text.

Bewerte ausschließlich danach, ob die Schülerantwort das grading_criterion erfüllt. \
Lexikalische Abweichungen zur example_answer sind erlaubt, solange das Kriterium erfüllt \
ist (z. B. "meiner Freundin" statt "meiner Schwester" für eine feminine Genitiv-Nominalphrase).

Großschreibungsregel:
- Wenn is_sentence_initial=true, MUSS die Schülerantwort mit einem Großbuchstaben \
  beginnen. Sonst ist die Antwort falsch, auch wenn die Morphologie stimmt.
- Wenn is_sentence_initial=false, spielt Großschreibung keine Rolle für die Bewertung — \
  beurteile rein die Morphologie/Lexik gegen das Kriterium.

Erfinde KEINE Toleranz, die nicht im Kriterium steht. Wenn das Kriterium eine bestimmte \
Form nennt, ist nur diese Form (oder genauso passende Alternativen für lexikalisch freie \
Lücken) korrekt.

Gib eine Punktzahl von 0.0 (völlig falsch) bis 1.0 (vollständig korrekt) und eine kurze \
Begründung auf Deutsch zurück.
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


async def judge_blank(
    *,
    question: str,
    blank: Blank,
    student_answer: str,
    llm: LLMService,
) -> JudgeResult:
    """Grade ONE student answer against ONE blank's criterion.

    Always traces as 'semantic_grading' — the reserved trace name for the
    grading-eval dashboard.
    """
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Frage: {question}\n"
                f"Kriterium: {blank.grading_criterion}\n"
                f"Beispielantwort: {blank.example_answer}\n"
                f"is_sentence_initial: {str(blank.is_sentence_initial).lower()}\n"
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
