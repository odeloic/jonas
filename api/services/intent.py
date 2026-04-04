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
IGNORE — Kurze Bestätigungen ("ok", "danke", "👍"), Begrüßungen ("hi", "hallo"), \
Smalltalk, themenfremde Nachrichten, oder nicht-deutsche Texte ohne Sprachbezug.

Regeln:
- Ein einzelnes deutsches Wort ohne Fragezeichen → IGNORE
- Ein einzelnes deutsches Wort mit Fragezeichen (z.B. "Dativ?") → QUESTION
- Deutsche Sätze mit 3+ Wörtern → PRACTICE (auch wenn korrekt)
- Fragen über Sprache (auch auf Englisch, z.B. "When do I use Akkusativ?") → QUESTION
- Emojis allein, "ok", "lol", "thanks", "hi" → IGNORE

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
