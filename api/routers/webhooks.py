import asyncio

import structlog
from fastapi import APIRouter, Request
from telegram import Update

from models.message import IncomingMessage

router = APIRouter()
log = structlog.get_logger()

_processed_updates: set[int] = set()
_MAX_TRACKED = 1000


@router.post("/webhook/telegram")
async def receive_telegram(request: Request):
    tg_app = request.app.state.tg_app
    data = await request.json()
    update = Update.de_json(data=data, bot=tg_app.bot)

    if update.update_id in _processed_updates:
        log.info("webhook_duplicate_skipped", update_id=update.update_id)
        return {"ok": True}

    _processed_updates.add(update.update_id)
    if len(_processed_updates) > _MAX_TRACKED:
        _processed_updates.clear()

    asyncio.create_task(tg_app.process_update(update))
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
