import structlog

from config import settings
from models.extraction import PageExtraction
from services.llm import complete_structured

log = structlog.get_logger()

EXTRACTION_SYSTEM_PROMPT = """\
You are a German language content extractor for a B2-level learner.

You receive a photo of a German textbook page or a screenshot of grammar material.
Extract ALL structured content visible on the page into the requested JSON format.

Rules:
- Extract grammar rules WITH their full explanations as written — do not summarize or rephrase.
- Extract every vocabulary item visible, including article and plural when shown.
- For each vocabulary item, provide a concise English translation in
definition_en, even if the page is German-only.
- Extract example sentences separately, with their annotation if one is given.
- If a field is not visible on the page, return null — never fabricate content.
- Set topic to the chapter or section heading if visible, otherwise your best description.
- Set source_notes only if the page is unusual (exercises only, a table with no explanation, etc.).
- All extracted text must be in German exactly as printed. Do not translate to English.
"""


async def extract_page(b64_image: str) -> PageExtraction:
    """Runs vision LLM extraction on a single base64-encoded image."""
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                },
                # {
                #   "type": "text",
                #   "text": "Extrahiere alle Inhalte von dieser Seite."
                # }
            ],
        },
    ]

    result = await complete_structured(
        messages, response_format=PageExtraction, model=settings.extraction_model, max_tokens=4096
    )

    log.info(
        "content_extracted",
        topic=result.topic,
        grammar_rules=len(result.grammar_rules),
        vocabulary=len(result.vocabulary),
        example_sentences=len(result.example_sentences),
    )

    return result
