import structlog

from config import settings
from db import async_session
from models.assignment import Assignment as AssignmentRow
from models.assignment_schema import (
    AdjektivDeklinationItem,
    AssignmentContent,
    CriterionItem,
    MultipleChoiceItem,
    ReorderItem,
)
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
- Alle Texte auf Deutsch
- instructions pro Abschnitt erklärt dem Lerner, was zu tun ist
- Items eines Abschnitts haben den gleichen type-Wert wie der Abschnitt

Übungstypen — verwende EXAKT die unten genannten Felder, keine alten Felder:

- REORDER (geschlossen, deterministisch geprüft):
  - correct_tokens = Liste der Wörter des korrekten Satzes in korrekter Reihenfolge, \
ohne Satzzeichen (Punkt/Komma weglassen). \
Groß-/Kleinschreibung wie im fertigen Satz.
  - Die korrekte Reihenfolge ist bindend — keine alternativen Vorfeld-Stellungen.
  - Beispiel: correct_tokens=["Ich","gehe","heute","ins","Kino"].

- MULTIPLE_CHOICE (geschlossen, deterministisch geprüft):
  - question = Frage oder Lückensatz, der nach der KORREKTEN Antwort fragt. \
NIE nach der falschen Option fragen (keine Formulierungen wie \
"Welche ist NICHT korrekt?", "Welche ist falsch?", "Welche ist inkorrekt?").
  - options = 3–4 plausible Optionen, nur eine korrekt.
  - correct_answer = die korrekte Option, BYTEGLEICH wie in options.

- ADJEKTIV_DEKLINATION (geschlossen, deterministisch geprüft):
  - question = Satz mit der Adjektiv-Lücke markiert durch ___ \
(z. B. "Der nett___ Mann lacht.").
  - correct_ending = die korrekte Endung als Suffix mit führendem Bindestrich \
(z. B. "-e", "-er", "-en", "-es", "-em").
  - candidate_endings = 3–5 plausible Endungen (Liste), die genau correct_ending enthält. \
Die UI rendert daraus einen Endungs-Wähler — KEIN Freitext-Input.

- COMPLETION (kriteriumbasiert, Judge-Bewertung):
  - question = Satz mit einer oder mehreren Lücken, markiert durch ___. \
Bei lexikalischer Vorgabe die Grundform in Klammern hinter der Lücke \
(z. B. "Ich helfe ___ (das Kind)."). Bei mehreren Lücken im Satz JEDE Lücke einzeln markieren.
  - grading_criterion = freie Beschreibung der Regel, die getestet wird, \
und was eine korrekte Antwort ausmacht. \
WENN das Item lexikalische Freiheit zulässt (z. B. "Genitiv einer femininen Person"), \
mach das im Kriterium explizit. \
WENN mehrere Lücken existieren, MUSS das Kriterium beschreiben, was JEDE Lücke verlangt.
  - example_answer = EINE mögliche Musterantwort. \
Bei mehreren Lücken die Antworten durch " / " trennen (z. B. "dem Kind / der Hausaufgabe"). \
Die example_answer wird dem Lerner bei falscher Antwort gezeigt — sie ist Beispiel, KEIN Anker.

- FILL_IN_THE_BLANK (kriteriumbasiert, Judge-Bewertung):
  - Gleiche Felder und Regeln wie COMPLETION. \
Verwende diesen Typ, wenn das fehlende Wort aus dem Kontext erschlossen werden muss \
(Vokabel / Konnektor) und keine reine Flexion getestet wird.

Wichtige Hinweise gegen typische Fehler:
- Verwende NIEMALS ein Feld "correct_answer" für REORDER, COMPLETION, FILL_IN_THE_BLANK \
oder ADJEKTIV_DEKLINATION. correct_answer existiert nur bei MULTIPLE_CHOICE.
- Wenn dieselbe Lücke morphologisch durch mehrere Worte ausgefüllt werden kann \
(z. B. Genitiv "meiner Schwester" vs. "meiner Mutter"), nutze einen kriteriumbasierten Typ \
(COMPLETION oder FILL_IN_THE_BLANK), nicht REORDER/MC.
- Bei ADJEKTIV_DEKLINATION nie die volle Form als correct_ending — nur das Suffix.
"""


def _fix_mc_item(item: MultipleChoiceItem) -> None:
    """Ensure correct_answer appears byte-exact in options."""
    if item.correct_answer in item.options:
        return
    if len(item.options) >= 4:
        item.options[-1] = item.correct_answer
    else:
        item.options.append(item.correct_answer)


def _sanitize_assignment(content: AssignmentContent) -> None:
    """Apply per-type structural fixes after generation.

    REORDER: strip empty tokens, ensure non-empty list.
    MULTIPLE_CHOICE: ensure correct_answer is byte-exact in options.
    ADJEKTIV_DEKLINATION: ensure correct_ending is in candidate_endings.
    Criterion items: validate non-empty criterion + example.
    """
    for section in content.sections:
        for item in section.items:
            if isinstance(item, ReorderItem):
                item.correct_tokens = [t for t in item.correct_tokens if t.strip()]
                if not item.correct_tokens:
                    raise ValueError("REORDER item has empty correct_tokens")
            elif isinstance(item, MultipleChoiceItem):
                _fix_mc_item(item)
            elif isinstance(item, AdjektivDeklinationItem):
                if item.correct_ending not in item.candidate_endings:
                    item.candidate_endings.append(item.correct_ending)
            elif isinstance(item, CriterionItem):
                if not item.grading_criterion.strip():
                    raise ValueError(f"{item.type} item has empty grading_criterion")
                if not item.example_answer.strip():
                    raise ValueError(f"{item.type} item has empty example_answer")
                if "___" not in item.question:
                    raise ValueError(f"{item.type} item has no ___ blank marker: {item.question!r}")


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
