from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import EventType, Geometry, Severity


class AlertOut(BaseModel):
    alert_id: str
    aoi_id: str
    event_type: EventType
    severity: Severity
    title: str
    message: str
    recommendations: list[str]
    affected_area_km2: float
    risk_cells: int
    geometry: Geometry | None = None
    issued_at: datetime
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
