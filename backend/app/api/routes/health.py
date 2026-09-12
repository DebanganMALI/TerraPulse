from fastapi import APIRouter

from app.config import settings
from app.services.pipeline import describe_pipeline

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = settings()
    return {"status": "ok", "version": s.version, **describe_pipeline()}
