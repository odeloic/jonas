import structlog
from fastapi import APIRouter, HTTPException

from services.llm import complete

router = APIRouter(prefix="/dev", tags=["dev"])
log = structlog.get_logger()


@router.post("/llm-ping")
async def llm_ping():
    try:
        reply = await complete(messages=[{"role": "user", "content": "Hallo, bist du Jonas?"}])
    except Exception as exc:
        log.error("llm_ping_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="LLM Call failed") from exc

    return {"reply": reply}
