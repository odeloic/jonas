from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from config import settings
from logging_config import configure_logging
from routers.health import router as health_router
from routers.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = structlog.get_logger()
    log.info("startup", service=settings.service_name, version=settings.version)
    yield
    log.info("shutdown", service=settings.service_name)


app = FastAPI(title=settings.service_name, version=settings.version, lifespan=lifespan)

app.include_router(health_router)
app.include_router(webhooks_router)
