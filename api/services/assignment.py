import structlog

from config import settings
from db import async_session
from models.assignment import Assignment as AssignmentRow
from models.assignment_schema import AssignmentContent
from models.extraction import PageExtraction
from services.llm import complete_structured

log = structlog.get_logger()

ASSIGNMENT_SYSTEM_PROMPT = """\
Du bist ein Deutschlehrer und erstellst Übungen für einen B2-Lerner.

Du erhältst Grammatikregeln aus einem Lehrbuch. Erstelle eine strukturierte Übung, \
die das Verständnis dieser Regeln testet.

Anforderungen:
- Mindestens 2 Abschnitte mit VERSCHIEDENEN Übungstypen
- 3–5 Aufgaben pro Abschnitt
- Jede Aufgabe hat GENAU EINE korrekte Antwort in correct_answer
- Alle Texte auf Deutsch
- instructions pro Abschnitt erklärt dem Lerner, was zu tun ist

Übungstypen:
- REORDER: Wörter in die richtige Reihenfolge bringen. \
question = durcheinander geworfene Wörter (mit " / " getrennt). \
correct_answer = der korrekte Satz.
- COMPLETION: Lücke mit der richtigen grammatischen Form füllen \
(Deklination, Konjugation, Kasus). \
question = Satz mit ___ für die Lücke + Grundform in Klammern. \
correct_answer = die korrekt flektierte Form.
- ADJEKTIV_DEKLINATION: Adjektivendung ergänzen. \
question = Satz mit Adjektiv ohne Endung + ___. \
correct_answer = Adjektiv mit korrekter Endung.
- FILL_IN_THE_BLANK: Fehlendes Wort aus dem Kontext erschließen. \
question = Satz mit ___. correct_answer = das fehlende Wort.
- MULTIPLE_CHOICE: Richtige Option wählen. \
question = Frage oder Lückensatz. options = 3–4 Optionen. \
correct_answer = die korrekte Option (muss in options enthalten sein).
"""


def _format_rules_context(extractions: list[PageExtraction]) -> str:
    """Format extracted grammar rules as plan-text context for the LLM"""
    parts = []
    for ext in extractions:
        parts.append(f"## Thema: {ext.topic}")
        for rule in ext.grammar_rules:
            parts.append(f"### {rule.rule_name}")
            parts.append(rule.explanation)
            if rule.pattern:
                parts.append(f"Muster: {rule.pattern}")
            if rule.examples:
                parts.append("Beispiele: " + " | ".join(rule.examples))
        parts.append("")
    return "\n".join(parts)


async def generate_assignment(
    extractions: list[PageExtraction],
    topic: str | None = None,
) -> AssignmentContent:
    """Generate a structured assignment from extracted grammar rules."""
    rules_context = _format_rules_context(extractions)
    resolved_topic = topic or extractions[0].topic

    user_content = (
        f"Erstelle Übungen zum Thema: {resolved_topic}\n\nGrammatikregeln:\n{rules_context}"
    )

    # Fallback: if no rules were extracted, generate from topic alone
    if not rules_context.strip():
        user_content = (
            f"Erstelle Übungen zum Thema: {resolved_topic}\n\n"
            "Keine Regeln vorhanden - erstelle Übungen nur basierend auf dem Thema."
        )
    result = await complete_structured(
        messages=[
            {"role": "system", "content": ASSIGNMENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=AssignmentContent,
        model=settings.assignment_model,
        max_tokens=4096,
    )

    log.info(
        "assignment_generated",
        topic=resolved_topic,
        sections=len(result.sections),
        total_items=sum(len(s.items) for s in result.sections),
    )

    return result


async def save_assignment(
    topic: str,
    content: AssignmentContent,
    grammar_rule_ids: list[int],
) -> AssignmentRow:
    """Persist assignment to Postgres"""
    async with async_session() as session:
        async with session.begin():
            row = AssignmentRow(
                type="GRAMMAR",
                topic=topic,
                content=content.model_dump(),
                grammar_rule_ids=grammar_rule_ids,
                source="TEACH",
            )
            session.add(row)
            await session.flush()
    log.info("assignment_saved", assignment_id=row.id, topic=topic)
    return row
