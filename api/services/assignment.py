import structlog

from config import settings
from db import async_session
from models.assignment import Assignment as AssignmentRow
from models.assignment_schema import AssignmentContent
from models.extraction import PageExtraction
from models.grammar_rule import GrammarRule as GrammarRuleRow
from models.learner_profile import LearnerProfile
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

ASSIGNMENT_SYSTEM_PROMPT = """\
<role>
Du bist ein Deutschlehrer und erstellst Übungen für einen B2-Lerner.
Alle Ausgaben auf Deutsch.
</role>

<task>
Du erhältst Grammatikregeln aus einem Lehrbuch. Erstelle eine strukturierte Übung,
die das Verständnis dieser Regeln testet.
</task>

<output_format>
- Mindestens 2 Abschnitte mit VERSCHIEDENEN Übungstypen.
- 3–5 Aufgaben pro Abschnitt.
- instructions pro Abschnitt erklärt dem Lerner, was zu tun ist.
- Feldnamen, Typen und Pflichtfelder ergeben sich aus dem JSON-Schema; halte dich strikt
  daran und erfinde keine zusätzlichen Felder.
</output_format>

<critical_invariant>
JEDES Item in section.items MUSS denselben type-Wert haben wie section.type.
Beispiel: Wenn section.type="MULTIPLE_CHOICE", dann MUSS für jedes Item gelten
  item.type="MULTIPLE_CHOICE".
Mische NIE verschiedene Item-Typen in einem Abschnitt. Für einen Abschnitt mit
gemischten Typen erstelle stattdessen zwei separate Abschnitte mit jeweils homogenen
Items. Eine Verletzung dieser Regel bricht das Schema-Validierungsverfahren ab.
</critical_invariant>

<exercise_types>

  <type name="REORDER" scoring="deterministic">
    <rule>
      Die UI zeigt Token-Chips in zufälliger Reihenfolge. Der Lerner muss sie in die
      korrekte Reihenfolge bringen. Die Reihenfolge in tokens[] ist die KORREKTE Reihenfolge
      (Index = Position im Zielsatz). Keine alternativen Vorfeld-Stellungen.
      tokens[].text ohne Satzzeichen; Groß-/Kleinschreibung wie im fertigen Satz.
    </rule>
    <good_examples>
      <example>
        tokens=[
          {"index":0,"text":"Ich"},
          {"index":1,"text":"gehe"},
          {"index":2,"text":"heute"},
          {"index":3,"text":"ins"},
          {"index":4,"text":"Kino"}
        ]
      </example>
    </good_examples>
  </type>

  <type name="MULTIPLE_CHOICE" scoring="deterministic">
    <rule>
      Frage nach der KORREKTEN Antwort, NIE nach der falschen Option. Verboten:
      "Welche ist NICHT korrekt?", "Welche ist falsch?", "Welche ist inkorrekt?".
      3–4 plausible Optionen, GENAU EINE is_correct=true.
    </rule>
    <good_examples>
      <example>
        question="Welcher Artikel passt zu 'Buch'?"
        options=[
          {"index":0,"text":"der","is_correct":false},
          {"index":1,"text":"die","is_correct":false},
          {"index":2,"text":"das","is_correct":true}
        ]
      </example>
    </good_examples>
  </type>

  <type name="COMPLETION" scoring="judge">
    <rule>
      Der Lerner gibt die vollständige(n) Antwortform(en) als Freitext ein. Der Judge
      bewertet JEDE Lücke einzeln gegen ihr grading_criterion. example_answer ist nur
      Illustration. Die question enthält KEINE ___ Marker — sie ist eine natürliche
      Aufforderung, die den Lemma/Grundformen frei nennt (z. B. das Verb, das Adjektiv
      oder die Nominalphrase, die dekliniert werden soll). blanks[] beschreibt jede Lücke
      in Reihenfolge.
    </rule>
    <blank_rules>
      <rule>
        grading_criterion nennt GENAU EINE korrekte Form (nicht "X oder einfach Y").
        Die erwartete Antwort ist immer die VOLLSTÄNDIGE inflektierte Wortform
        (z. B. "nette", "Singen", "dem Kind") — nie nur ein Suffix.
      </rule>
      <rule>
        is_sentence_initial=true heißt: die Antwort dieser Lücke ist das ERSTE Wort
        des Zielsatzes. Dann MUSS die korrekte Form großgeschrieben sein, und das
        Kriterium nennt die großgeschriebene Form. Sonst spielt Großschreibung keine
        Rolle.
      </rule>
      <rule>
        Wenn die Lücke lexikalisch frei ist (z. B. "Genitiv einer femininen Person"),
        nenne diese Freiheit im Kriterium. example_answer bleibt EIN Beispiel.
      </rule>
    </blank_rules>
    <good_examples>
      <example label="Adjektivdeklination — Freitext der vollen Form">
        question="Setze die korrekte Form von 'nett' ein: 'Der ___ Mann lacht.'"
        blanks=[
          {
            "index":0,
            "grading_criterion":"Adjektiv 'nett' korrekt dekliniert nach
              bestimmtem Artikel 'der' (Nom. Sg. Mask., schwache Deklination): 'nette'.",
            "example_answer":"nette",
            "is_sentence_initial":false
          }
        ]
      </example>
      <example label="Imperativ am Satzanfang">
        question="Bilde den Imperativ wir-Form von 'singen', um zusammen zu singen."
        blanks=[
          {
            "index":0,
            "grading_criterion":"Imperativ wir-Form von 'singen', großgeschrieben
              am Satzanfang: 'Singen'.",
            "example_answer":"Singen wir zusammen!",
            "is_sentence_initial":true
          }
        ]
      </example>
      <example label="Lexikalisch frei — feminine Genitivphrase">
        question="Setze ein Genitivattribut (feminine Person) ein:
          'Die Tasche ___ ist moderner als meine.'"
        blanks=[
          {
            "index":0,
            "grading_criterion":"Genitiv einer femininen Person. Jede grammatisch
              korrekte feminine Genitiv-Nominalphrase ist akzeptabel
              (z. B. 'meiner Schwester', 'meiner Freundin').",
            "example_answer":"meiner Schwester",
            "is_sentence_initial":false
          }
        ]
      </example>
      <example label="Mehrere Lücken">
        question="Setze Dativ und Genitiv ein: helfen + 'das Kind';
          wegen + 'die Hausaufgabe'."
        blanks=[
          {
            "index":0,
            "grading_criterion":"Dativ Singular Neutrum von 'das Kind' — 'dem Kind'.",
            "example_answer":"dem Kind",
            "is_sentence_initial":false
          },
          {
            "index":1,
            "grading_criterion":"Genitiv Singular Femininum von 'die Hausaufgabe'
              — 'der Hausaufgabe'.",
            "example_answer":"der Hausaufgabe",
            "is_sentence_initial":false
          }
        ]
      </example>
    </good_examples>
    <bad_examples>
      <example reason="zwei Formen im Kriterium">
        grading_criterion="Das Verb 'öffnen' wird zu 'öffne' oder einfach 'Öffne' im Imperativ."
      </example>
      <example reason="Kriterium ist Tautologie">
        grading_criterion="Das Verb 'singen' wird zu 'singen'."
      </example>
      <example reason="erwartete Antwort ist nur ein Suffix — der Lerner gibt aber Freitext ein">
        example_answer="-e"
      </example>
      <example reason="___ in der question — alte Konvention, gehört nicht mehr in question">
        question="___ (singen) wir zusammen!"
      </example>
    </bad_examples>
  </type>

  <type name="FILL_IN_THE_BLANK" scoring="judge">
    <rule>
      Gleiche Regeln wie COMPLETION (auch <blank_rules>). Verwende diesen Typ, wenn das
      fehlende Wort aus dem Kontext erschlossen werden muss (Vokabel / Konnektor) und
      keine reine Flexion getestet wird.
    </rule>
  </type>

</exercise_types>

<common_mistakes>
- Item-Typ ≠ Section-Typ: häufigster Fehler. Items in section.items MÜSSEN denselben
  type-Wert haben wie section.type. Bei gemischten Typen: separate Abschnitte erstellen.
- Erwartete Antworten sind IMMER vollständige inflektierte Wortformen, nie Suffixe
  oder Stämme. Falsch: example_answer="-e". Richtig: example_answer="nette".
- COMPLETION/FILL_IN_THE_BLANK: question enthält KEINE ___ Marker und KEINE
  "(grundform)"-Klammern. Nenne die Grundform stattdessen natürlich im Satz
  (z. B. "Setze die korrekte Form von 'nett' ein...").
- Wenn dieselbe Lücke morphologisch durch mehrere Worte ausgefüllt werden kann
  (z. B. Genitiv "meiner Schwester" vs. "meiner Mutter"), nutze COMPLETION oder
  FILL_IN_THE_BLANK mit explizit lexikalisch freiem Kriterium.
</common_mistakes>
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


_EMPTY_RESULT_NUDGE = (
    "Deine vorherige Antwort enthielt keine Aufgaben (items war leer). "
    "Erstelle jetzt die Übungen wirklich: mindestens 2 Abschnitte mit je 3–5 Items. "
    "Antworte ausschließlich mit gültigem JSON gemäß Schema."
)


def _total_items(content: AssignmentContent) -> int:
    return sum(len(s.items) for s in content.sections)


async def _generate_with_empty_retry(
    system_prompt: str,
    user_content: str,
    trace_name: str,
    max_empty_retries: int = 2,
) -> AssignmentContent:
    """Call the LLM and retry if it returns schema-valid but item-empty output."""
    attempt_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    for attempt in range(max_empty_retries + 1):
        result = (
            await _llm.complete_structured(
                messages=attempt_messages,
                response_format=AssignmentContent,
                model=settings.assignment_model,
                max_tokens=4096,
                trace_name=trace_name,
            )
        ).parsed
        if _total_items(result) > 0:
            return result
        if attempt >= max_empty_retries:
            log.error(
                "assignment_generation_empty_exhausted",
                trace_name=trace_name,
                attempts=attempt + 1,
            )
            return result
        log.warning(
            "assignment_generation_empty_retry",
            trace_name=trace_name,
            attempt=attempt + 1,
        )
        attempt_messages = attempt_messages + [{"role": "user", "content": _EMPTY_RESULT_NUDGE}]
    raise RuntimeError("_generate_with_empty_retry exited loop unexpectedly")


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

    result = await _generate_with_empty_retry(
        system_prompt=system_prompt,
        user_content=user_content,
        trace_name="assignment_generation",
    )

    log.info(
        "assignment_generated",
        topic=resolved_topic,
        sections=len(result.sections),
        total_items=_total_items(result),
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

    result = await _generate_with_empty_retry(
        system_prompt=system_prompt,
        user_content=user_content,
        trace_name="assignment_generation_from_rules",
    )

    log.info(
        "assignment_generated_from_rules",
        topic=resolved_topic,
        sections=len(result.sections),
        total_items=_total_items(result),
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
