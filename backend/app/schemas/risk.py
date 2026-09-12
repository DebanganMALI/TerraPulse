from pydantic import BaseModel

from app.schemas.analysis import RiskDriver
from app.schemas.common import EventType, RiskLevel, Unit


class RiskProperties(BaseModel):
    cell_id: str
    aoi_id: str
    risk_score: Unit
    risk_level: RiskLevel
    primary_risk: EventType
    drivers: list[RiskDriver]


class StatsOut(BaseModel):
    aoi_id: str
    total_events: int
    total_changed_area_km2: float
    by_event_type: dict[str, int]
    risk_distribution: dict[str, int]
    highest_risk_score: float
    open_alerts: int
    last_analysis_at: str | None = None
