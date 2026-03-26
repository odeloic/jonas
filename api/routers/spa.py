from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

log = structlog.get_logger()

SPA_DIR = Path("/srv/spa")

router = APIRouter()


def mount_spa(app):
    if not SPA_DIR.is_dir():
        log.info("spa_skip", reason="static dir not found")
        return
    assets = SPA_DIR / "assets"
    if assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets)),
            name="spa-assets",
        )
    log.info("spa_mounted", path=str(SPA_DIR))


@router.get("/{path:path}")
async def serve_spa(path: str):
    if not SPA_DIR.is_dir():
        return JSONResponse({"error": "SPA not built"}, status_code=404)
    file = SPA_DIR / path
    if path and file.is_file():
        return FileResponse(str(file))
    return FileResponse(str(SPA_DIR / "index.html"))
