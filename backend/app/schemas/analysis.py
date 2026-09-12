from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    AOI_ID_PATTERN,
    JOB_ID_PATTERN,
    EventType,
    Geometry,
    JobStatus,
    Provider,
    RiskLevel,
    Unit,
)


class AnalysisRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aoi_id: str = Field(pattern=AOI_ID_PATTERN)
    provider: Provider = Provider.local


class JobOut(BaseModel):
    job_id: str
    aoi_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    counts: dict[str, int] = {"events": 0, "risk_cells": 0, "alerts": 0}


# --------------------------------------------------------------------------
# the A <-> B seam. Part B implements run_analysis(AnalysisRequest) -> AnalysisResult
# --------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aoi_id: str = Field(pattern=AOI_ID_PATTERN)
    provider: Provider = Provider.local
    job_id: str = Field(pattern=JOB_ID_PATTERN)


class DetectedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    confidence: Unit
    area_km2: float = Field(ge=0)
    centroid: tuple[float, float]  # (lat, lon)
    geometry: Geometry
    deltas: dict[str, float | None] = {}


class RiskDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    contribution: Unit


class RiskCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: str
    risk_score: Unit
    risk_level: RiskLevel
    primary_risk: EventType
    geometry: Geometry
    drivers: list[RiskDriver] = []


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aoi_id: str = Field(pattern=AOI_ID_PATTERN)
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    events: list[DetectedEvent] = []
    risk_cells: list[RiskCell] = []
    overlays: dict[str, str] = {}
    model_info: dict[str, str] = {}
    warnings: list[str] = []
