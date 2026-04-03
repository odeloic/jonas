import asyncio
import base64

import structlog
from telegram import Bot

from config import settings
from models.triage import ImageCategory, TriageResponse, TriageResult
from services.llm_service import LLMService

log = structlog.get_logger()
_llm = LLMService()

TRIAGE_PROMPT = """\
You are an image classifier for a German language learning app.

For each image, classify it as exactly one of:
- BOOK_PAGE - a photo of a German text
- GRAMMAR_SCREENSHOT - a screenshot of German grammar rules, tables or exercises
- OTHER - anything else (selfies, memes, unrelated content, anything that doesn't fit above)
"""


async def download_photos_as_base64(bot: Bot, file_ids: list[str]) -> list[tuple[str, str]]:
    """Download Telegram photos concurrently. Returns (file_id, base64_data) tuples."""

    async def _download(file_id: str) -> tuple[str, str]:
        tg_file = await bot.get_file(file_id)
        data = await tg_file.download_as_bytearray()
        return (file_id, base64.b64encode(bytes(data)).decode())

    return list(await asyncio.gather(*[_download(fid) for fid in file_ids]))


async def triage_images(
    base64_images: list[tuple[str, str]],
) -> list[TriageResult]:
    """Classify images via a single vision LLM call."""
    n = len(base64_images)

    content: list[dict] = [
        {
            "type": "text",
            "text": f"{TRIAGE_PROMPT}\nThere are {n} images. Return exactly {n} classifications.",
        }
    ]
    for _file_id, b64 in base64_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )

    messages = [{"role": "user", "content": content}]

    result = (
        await _llm.complete_structured(
            messages,
            response_format=TriageResponse,
            model=settings.triage_model,
            max_tokens=512,
            trace_name="triage",
        )
    ).parsed

    if len(result.classifications) != n:
        log.warning("triage_count_mismatch", expected=n, got=len(result.classifications))
        raise ValueError("Triage returned wrong number of classifications")

    log.info(
        "vision_triage_complete",
        total=n,
        categories={
            c.value: sum(1 for x in result.classifications if x.category == c)
            for c in ImageCategory
        },
    )

    return [
        TriageResult(file_id=file_id, category=result.classifications[i].category)
        for i, (file_id, _) in enumerate(base64_images)
    ]
