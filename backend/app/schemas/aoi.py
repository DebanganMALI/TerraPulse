from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import AOI_ID_PATTERN, EventType, Provider


class AoiOut(BaseModel):
    aoi_id: str = Field(pattern=AOI_ID_PATTERN)
    name: str
    region: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    center: tuple[float, float]  # (lat, lon)
    before_date: date
    after_date: date
    provider: Provider = Provider.local
    expected_event: EventType | None = None
    preview_before_url: str | None = None
    preview_after_url: str | None = None

    @field_validator("bbox")
    @classmethod
    def _bbox_ordered(cls, v: list[float]) -> list[float]:
        min_lon, min_lat, max_lon, max_lat = v
        if not (-180 <= min_lon < max_lon <= 180):
            raise ValueError("bbox longitudes out of range or unordered")
        if not (-90 <= min_lat < max_lat <= 90):
            raise ValueError("bbox latitudes out of range or unordered")
        return v


class SceneMeta(BaseModel):
    """Shape of data/scenes/<aoi_id>/meta.json, written by Part B."""

    aoi_id: str = Field(pattern=AOI_ID_PATTERN)
    name: str
    region: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    center: tuple[float, float]
    before_date: date
    after_date: date
    provider: Provider = Provider.local
    expected_event: EventType | None = None
    band_map: dict[str, int] = {}
