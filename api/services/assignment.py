import random
import re

import structlog

from config import settings
from db import async_session
from models.assignment import Assignment as AssignmentRow
from models.assignment_schema import AssignmentContent, AssignmentItem, SectionType
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from models.learner_profile import LearnerProfile
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

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
question = ALLE Wörter des Satzes in zufälliger Reihenfolge, mit " / " getrennt. \
Satzzeichen (Punkt, Komma) NICHT als Shuffle-Token aufnehmen — \
Satzzeichen gehören nur in correct_answer. \
Jedes Wort aus correct_answer muss in question stehen (auch doppelte wie "ich", "der", "die"), \
und kein Wort darf in question stehen, das nicht in correct_answer vorkommt. \
correct_answer = der korrekte Satz mit korrekter Groß-/Kleinschreibung und Satzzeichen.
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
question = Frage oder Lückensatz, die nach der KORREKTEN Antwort fragt. \
Frage NIE nach der falschen/nicht-korrekten Option \
(keine Formulierungen wie "Welche ist NICHT korrekt?", \
"Welche ist falsch?", "Welche ist inkorrekt?"). \
options = 3–4 Optionen, alle plausibel, aber nur eine korrekt. \
correct_answer = die korrekte Option, BYTEGLEICH wie in options \
(gleiche Groß-/Kleinschreibung, gleiche Satzzeichen, gleiche Leerzeichen). \
WICHTIG: correct_answer MUSS exakt einer der options entsprechen — \
kopiere den Text der richtigen Option direkt in correct_answer.
"""


def _derive_reorder_question(correct_answer: str) -> str:
    """Build a scrambled word list from the answer, guaranteed to bag-match the eval check.

    Derives question tokens from correct_answer rather than trusting the LLM to copy them —
    making the REORDER bag invariant hold by construction (the eval check becomes tautological
    for this invariant, but still catches empty fields and other structural issues).
    """
    words = [re.sub(r"[^\w]", "", w) for w in correct_answer.split()]
    words = [w for w in words if w]
    random.shuffle(words)
    return " / ".join(words)


def _fix_mc_item(item: AssignmentItem) -> None:
    """Ensure correct_answer appears byte-exact in options, replacing the last distractor if not."""
    if not item.options or item.correct_answer in item.options:
        return
    if len(item.options) >= 4:
        item.options[-1] = item.correct_answer
    else:
        item.options.append(item.correct_answer)


def _sanitize_assignment(content: AssignmentContent) -> None:
    for section in content.sections:
        for item in section.items:
            if section.type == SectionType.REORDER:
                item.question = _derive_reorder_question(item.correct_answer)
            elif section.type == SectionType.MULTIPLE_CHOICE:
                _fix_mc_item(item)


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


def _format_learner_context(profile: LearnerProfile) -> str:
    """Build a German-language learner context block for the system prompt."""
    weak = profile.weak_topics or {}
    sorted_weak = sorted(weak.items(), key=lambda x: x[1]["error_count"], reverse=True)[:3]
    weak_lines = ", ".join(f"{t} ({d['error_count']} Fehler)" for t, d in sorted_weak)

    return (
        f"\nLernerprofil:\n"
        f"- Geschätztes Niveau: {profile.cefr_estimate}\n"
        f"- Schwache Themen (häufige Fehler): {weak_lines or 'keine'}\n"
        f"\nBerücksichtige:\n"
        f"- Erstelle mehr Aufgaben zu den schwachen Themen.\n"
        f"- Passe die Schwierigkeit an das Niveau ({profile.cefr_estimate}) an.\n"
        f"- Reduziere Aufgaben zu bereits beherrschten Themen.\n"
    )


async def generate_assignment(
    extractions: list[PageExtraction],
    topic: str | None = None,
    learner_profile: LearnerProfile | None = None,
) -> AssignmentContent:
    """Generate a structured assignment from extracted grammar rules."""
    rules_context = _format_rules_context(extractions)
    resolved_topic = topic or extractions[0].topic

    system_prompt = ASSIGNMENT_SYSTEM_PROMPT
    if learner_profile and learner_profile.weak_topics:
        system_prompt += _format_learner_context(learner_profile)

    user_content = (
        f"Erstelle Übungen zum Thema: {resolved_topic}\n\nGrammatikregeln:\n{rules_context}"
    )

    # Fallback: if no rules were extracted, generate from topic alone
    if not rules_context.strip():
        user_content = (
            f"Erstelle Übungen zum Thema: {resolved_topic}\n\n"
            "Keine Regeln vorhanden - erstelle Übungen nur basierend auf dem Thema."
        )
    result = (
        await _llm.complete_structured(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=AssignmentContent,
            model=settings.assignment_model,
            max_tokens=4096,
            trace_name="assignment_generation",
        )
    ).parsed

    _sanitize_assignment(result)

    log.info(
        "assignment_generated",
        topic=resolved_topic,
        sections=len(result.sections),
        total_items=sum(len(s.items) for s in result.sections),
    )

    return result


def _format_db_rules_context(rules: list[GrammarRuleRow]) -> str:
    """Format DB GrammarRule rows as plain-text context for the LLM."""
    parts = []
    for rule in rules:
        parts.append(f"## Thema: {rule.topic}")
        parts.append(f"### {rule.rule_name}")
        parts.append(rule.explanation)
        if rule.pattern:
            parts.append(f"Muster: {rule.pattern}")
        if rule.examples:
            parts.append("Beispiele: " + " | ".join(rule.examples))
        parts.append("")
    return "\n".join(parts)


async def generate_assignment_from_rules(
    rules: list[GrammarRuleRow],
    topic: str | None = None,
    learner_profile: LearnerProfile | None = None,
) -> AssignmentContent:
    """Generate assignment from DB grammar rules (no PageExtraction needed)."""
    rules_context = _format_db_rules_context(rules)
    resolved_topic = topic or rules[0].topic

    system_prompt = ASSIGNMENT_SYSTEM_PROMPT
    if learner_profile and learner_profile.weak_topics:
        system_prompt += _format_learner_context(learner_profile)

    user_content = (
        f"Erstelle Übungen zum Thema: {resolved_topic}\n\nGrammatikregeln:\n{rules_context}"
    )

    result = (
        await _llm.complete_structured(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=AssignmentContent,
            model=settings.assignment_model,
            max_tokens=4096,
            trace_name="assignment_generation_from_rules",
        )
    ).parsed

    _sanitize_assignment(result)

    log.info(
        "assignment_generated_from_rules",
        topic=resolved_topic,
        sections=len(result.sections),
        total_items=sum(len(s.items) for s in result.sections),
        rule_count=len(rules),
    )

    return result


async def save_assignment(
    topic: str,
    content: AssignmentContent,
    grammar_rule_ids: list[int],
    telegram_chat_id: str | None = None,
    source: str = "TEACH",
) -> AssignmentRow:
    """Persist assignment to Postgres"""
    async with async_session() as session:
        async with session.begin():
            row = AssignmentRow(
                type="GRAMMAR",
                topic=topic,
                content=content.model_dump(),
                grammar_rule_ids=grammar_rule_ids,
                telegram_chat_id=telegram_chat_id,
                source=source,
            )
            session.add(row)
            await session.flush()
    log.info("assignment_saved", assignment_id=row.id, topic=topic, source=source)
    return row
