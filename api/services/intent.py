import structlog

from models.intent import IntentResult
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

_SYSTEM_PROMPT = """\
Du bist ein Intent-Klassifikator für einen Deutsch-Tutor-Bot.
Klassifiziere die Nachricht des Nutzers in genau eine Kategorie:

PRACTICE — Der Nutzer hat einen deutschen Satz geschrieben (auch mit Fehlern), \
der korrigiert werden soll. Das ist der häufigste Fall.
QUESTION — Der Nutzer stellt eine Frage über Grammatik, Vokabeln oder die \
deutsche Sprache (auf Deutsch oder Englisch).
IGNORE — *Ausschließlich* Nachrichten ohne sprachlichen Übungsinhalt: \
reine Bestätigungen ("ok", "danke", "👍"), reine Begrüßungen ("hi", "hallo" \
ganz allein), themenfremder englischer Smalltalk, oder Emojis allein.

Priorität (wichtig):
- Wenn die Nachricht IRGENDEINEN deutschen Satzversuch enthält (über eine reine \
Begrüßung hinaus), immer PRACTICE — auch wenn sie mit "Hallo" oder "Hi" \
anfängt. Eine Begrüßung macht die Nachricht NICHT zu IGNORE.
- Im Zweifel zwischen PRACTICE und IGNORE → PRACTICE.
- Im Zweifel zwischen QUESTION und IGNORE → QUESTION.

Regeln:
- Ein einzelnes deutsches Wort ohne Fragezeichen → IGNORE
- Ein einzelnes deutsches Wort mit Fragezeichen (z.B. "Dativ?", "hallo?") → QUESTION
- Deutsche Sätze mit 3+ Wörtern → PRACTICE (auch wenn korrekt, auch mit \
Begrüßungs-Präfix)
- Fragen über Sprache (auch auf Englisch, z.B. "When do I use Akkusativ?") → QUESTION
- Emojis allein, "ok", "lol", "thanks", reines "hi"/"hallo" ohne weiteren \
Inhalt → IGNORE

Beispiele:
- "Hallo Judith, wie geht's dir? Über morgen, weiß oder rot Wein?" → PRACTICE \
(enthält deutsche Sätze, auch wenn sie mit Begrüßung beginnen)
- "Hi! Ich habe gestern ein Film gesehen." → PRACTICE
- "hallo" → IGNORE
- "hallo?" → QUESTION (Einzelwort mit Fragezeichen)
- "danke" → IGNORE

Antworte mit dem Intent und deiner Konfidenz (0-1).\
"""


async def classify_intent(user_text: str) -> IntentResult:
    """Classify a user message as PRACTICE, QUESTION, or IGNORE."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    result = await _llm.complete_structured(
        messages=messages,
        response_format=IntentResult,
        trace_name="intent_classification",
    )
    log.info(
        "intent_classified",
        intent=result.parsed.intent,
        confidence=result.parsed.confidence,
        text_preview=user_text[:50],
    )
    return result.parsed
