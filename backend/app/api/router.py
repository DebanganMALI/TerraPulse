from fastapi import APIRouter

from app.api.routes import alerts, analysis, aoi, auth, events, health, risk

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(aoi.router)
api_router.include_router(analysis.router)
api_router.include_router(events.router)
api_router.include_router(risk.router)
api_router.include_router(alerts.router)
