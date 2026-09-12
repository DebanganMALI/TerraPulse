from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import EventType, Severity, Unit


class EventProperties(BaseModel):
    event_id: str
    aoi_id: str
    event_type: EventType
    confidence: Unit
    severity: Severity
    area_km2: float
    centroid: tuple[float, float]  # (lat, lon)
    deltas: dict[str, float | None]
    detected_at: datetime
    job_id: str
