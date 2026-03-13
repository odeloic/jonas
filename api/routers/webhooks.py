import structlog
from fastapi import APIRouter, Request
from telegram import Update

from models.message import IncomingMessage

router = APIRouter()
log = structlog.get_logger()


@router.post("/webhook/telegram")
async def receive_telegram(request: Request):
    tg_app = request.app.state.tg_app
    data = await request.json()
    update = Update.de_json(data=data, bot=tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}


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
