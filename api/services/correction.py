import structlog

from models.correction import CorrectionResult
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

_CORRECTION_SYSTEM_PROMPT = """\
Du bist Jonas, ein freundlicher Deutsch-Tutor auf B2-Niveau.

Deine Aufgabe: Korrigiere den deutschen Satz des Lerners.

{rules_block}

Regeln:
- Wenn der Satz Fehler enthält: setze has_error=true, gib den korrigierten Satz an, \
benenne den Fehlertyp und erkläre den Fehler auf Deutsch. \
Beziehe dich dabei auf die Grammatikregeln, wenn vorhanden.
- Wenn der Satz korrekt ist: setze has_error=false, corrected=null, error_type=null, \
und lobe den Lerner kurz.
- Stelle immer eine Anschlussfrage (follow_up), um das Gespräch fortzusetzen.
- Sei ermutigend und freundlich.\
"""

_RULES_WITH_CONTEXT = """\
Nutze die folgenden Grammatikregeln als Referenz für deine Korrektur:

{rules_text}

Beziehe dich in deiner Erklärung auf die passende Regel.\
"""

_RULES_WITHOUT_CONTEXT = """\
Du hast keine spezifischen Grammatikregeln als Referenz. \
Korrigiere trotzdem anhand deines Wissens über deutsche Grammatik.\
"""

_QUESTION_SYSTEM_PROMPT = """\
Du bist Jonas, ein freundlicher Deutsch-Tutor auf B2-Niveau.

Der Lerner stellt eine Frage über die deutsche Sprache.
Beantworte sie klar und verständlich auf Deutsch.

{rules_block}

Regeln:
- Antworte immer auf Deutsch, auch wenn die Frage auf Englisch gestellt wurde.
- Gib Beispiele, wenn es hilft.
- Beziehe dich auf die Grammatikregeln, wenn sie relevant sind.
- Sei freundlich und ermutigend.\
"""


def _format_rules_block(grammar_rules: list[dict]) -> str:
    if not grammar_rules:
        return _RULES_WITHOUT_CONTEXT

    parts = []
    for i, rule in enumerate(grammar_rules, 1):
        lines = [f"{i}. {rule.get('rule_name', 'Regel')} ({rule.get('topic', '')})"]
        if rule.get("explanation"):
            lines.append(f"   Erklärung: {rule['explanation']}")
        if rule.get("examples"):
            lines.append(f"   Beispiele: {' | '.join(rule['examples'][:3])}")
        parts.append("\n".join(lines))

    rules_text = "\n\n".join(parts)
    return _RULES_WITH_CONTEXT.format(rules_text=rules_text)


async def correct_german_text(user_text: str, grammar_rules: list[dict]) -> CorrectionResult:
    """Correct a German text using retrieved grammar rules as context."""
    rules_block = _format_rules_block(grammar_rules)
    system_prompt = _CORRECTION_SYSTEM_PROMPT.format(rules_block=rules_block)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    result = await _llm.complete_structured(
        messages=messages,
        response_format=CorrectionResult,
        trace_name="practice_correction",
    )
    log.info(
        "correction_done",
        has_error=result.parsed.has_error,
        error_type=result.parsed.error_type,
    )
    return result.parsed


async def answer_question(user_text: str, grammar_rules: list[dict]) -> str:
    """Answer a grammar/language question using retrieved rules as context."""
    rules_block = _format_rules_block(grammar_rules)
    system_prompt = _QUESTION_SYSTEM_PROMPT.format(rules_block=rules_block)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    result = await _llm.complete(
        messages=messages,
        trace_name="practice_question",
    )
    log.info("question_answered", text_preview=user_text[:50])
    return result.parsed
