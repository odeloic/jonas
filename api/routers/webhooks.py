import structlog
from fastapi import APIRouter, Request

from models.message import IncomingMessage

router = APIRouter()
log = structlog.get_logger()


@router.post("/webhook/whatsapp")
async def receive_whatsapp(payload: IncomingMessage, request: Request):
    # TODO(M2): validate X-Hub-Signature-256 header before processing
    log.info(
        "webhook_received",
        channel="whatsapp",
        object=payload.object,
        entry_count=len(payload.entry),
    )
    return {"received": True}
