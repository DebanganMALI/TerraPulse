from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AOI_ID_PATTERN = r"^[a-z0-9_]{3,48}$"
JOB_ID_PATTERN = r"^job_[a-f0-9]{6}$"

AoiId = Annotated[str, Field(pattern=AOI_ID_PATTERN)]
JobId = Annotated[str, Field(pattern=JOB_ID_PATTERN)]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]


class Role(StrEnum):
    viewer = "viewer"
    analyst = "analyst"
    authority = "authority"


# ordering, not equality: authority inherits everything analyst can do
ROLE_ORDER: dict[Role, int] = {Role.viewer: 0, Role.analyst: 1, Role.authority: 2}


class EventType(StrEnum):
    flood = "flood"
    deforestation = "deforestation"
    wildfire_burn = "wildfire_burn"
    urban_expansion = "urban_expansion"
    water_recession = "water_recession"
    no_change = "no_change"


class Severity(StrEnum):
    info = "info"
    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.info: 0,
    Severity.low: 1,
    Severity.moderate: 2,
    Severity.high: 3,
    Severity.severe: 4,
}


class RiskLevel(StrEnum):
    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"


RISK_LEVEL_ORDER: dict[RiskLevel, int] = {
    RiskLevel.low: 0,
    RiskLevel.moderate: 1,
    RiskLevel.high: 2,
    RiskLevel.severe: 3,
}

RISK_THRESHOLDS: list[tuple[float, RiskLevel]] = [
    (0.75, RiskLevel.severe),
    (0.50, RiskLevel.high),
    (0.25, RiskLevel.moderate),
    (0.00, RiskLevel.low),
]


def risk_level_for(score: float) -> RiskLevel:
    for floor, level in RISK_THRESHOLDS:
        if score >= floor:
            return level
    return RiskLevel.low


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Provider(StrEnum):
    local = "local"
    sentinel = "sentinel"


class ErrorCode(StrEnum):
    invalid_credentials = "INVALID_CREDENTIALS"
    token_expired = "TOKEN_EXPIRED"
    forbidden_role = "FORBIDDEN_ROLE"
    aoi_not_found = "AOI_NOT_FOUND"
    job_not_found = "JOB_NOT_FOUND"
    job_already_running = "JOB_ALREADY_RUNNING"
    alert_not_found = "ALERT_NOT_FOUND"
    rate_limited = "RATE_LIMITED"
    pipeline_failed = "PIPELINE_FAILED"
    validation_error = "VALIDATION_ERROR"
    internal_error = "INTERNAL_ERROR"


class ErrorResponse(BaseModel):
    detail: str
    code: ErrorCode
    request_id: str | None = None


class Geometry(BaseModel):
    """Minimal RFC 7946 geometry. Coordinates are [lon, lat], WGS84."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: Geometry
    properties: dict[str, Any]


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]


class BBox(BaseModel):
    """[min_lon, min_lat, max_lon, max_lat]"""

    model_config = ConfigDict(extra="forbid")

    min_lon: float = Field(ge=-180, le=180)
    min_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)

    @classmethod
    def from_list(cls, v: list[float]) -> "BBox":
        return cls(min_lon=v[0], min_lat=v[1], max_lon=v[2], max_lat=v[3])

    def to_list(self) -> list[float]:
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]
