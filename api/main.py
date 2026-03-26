from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from channels.telegram import build_app
from config import settings
from logging_config import configure_logging
from routers.assignments import router as assignments_router
from routers.dev import router as dev_router
from routers.health import router as health_router
from routers.spa import mount_spa
from routers.spa import router as spa_router
from routers.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if "anthropic" in settings.default_model and not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required"  # FIXME: generalize
        )
    log = structlog.get_logger()
    log.info("startup", service=settings.service_name, version=settings.version)

    tg_app = build_app()
    await tg_app.initialize()
    await tg_app.start()

    webhook_url = f"{settings.telegram_webhook_base_url}/webhook/telegram"
    await tg_app.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    log.info("telegram_webhook_set", url=webhook_url)

    app.state.tg_app = tg_app

    yield

    await tg_app.bot.delete_webhook()
    await tg_app.stop()
    await tg_app.shutdown()
    log.info("shutdown", service=settings.service_name)


app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)

app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(dev_router)
app.include_router(assignments_router)

mount_spa(app)
app.include_router(spa_router)
