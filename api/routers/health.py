from fastapi import APIRouter

from config import settings

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name, "version": settings.version}
