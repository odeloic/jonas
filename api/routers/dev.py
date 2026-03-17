import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.extraction import PageExtraction
from services.content_extraction import extract_page
from services.llm import complete

router = APIRouter(prefix="/dev", tags=["dev"])
log = structlog.get_logger()


class ExtractRequest(BaseModel):
    image_base64: str


@router.post("/llm-ping")
async def llm_ping():
    try:
        reply = await complete(messages=[{"role": "user", "content": "Hallo, bist du Jonas?"}])
    except Exception as exc:
        log.error("llm_ping_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="LLM Call failed") from exc

    return {"reply": reply}


@router.post("/extract")
async def dev_extract(req: ExtractRequest) -> PageExtraction:
    try:
        result = await extract_page(req.image_base64)
    except Exception as exc:
        log.error("dev_extract_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    return result
