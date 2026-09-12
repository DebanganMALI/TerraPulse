from fastapi import APIRouter, Query
from sqlalchemy import select

from app.db.models import Event
from app.schemas.common import AOI_ID_PATTERN, Feature, FeatureCollection, Geometry
from app.security.deps import CurrentUser, DbDep

router = APIRouter(tags=["results"])


@router.get("/events", response_model=FeatureCollection)
def events(
    db: DbDep,
    user: CurrentUser,
    aoi_id: str = Query(pattern=AOI_ID_PATTERN),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
) -> FeatureCollection:
    rows = db.scalars(
        select(Event)
        .where(Event.aoi_id == aoi_id, Event.confidence >= min_confidence)
        .order_by(Event.area_km2.desc())
    ).all()

    return FeatureCollection(
        features=[
            Feature(
                geometry=Geometry.model_validate(r.geometry),
                properties={
                    "event_id": r.event_id,
                    "aoi_id": r.aoi_id,
                    "event_type": r.event_type,
                    "confidence": r.confidence,
                    "severity": r.severity,
                    "area_km2": r.area_km2,
                    "centroid": [r.centroid_lat, r.centroid_lon],
                    "deltas": r.deltas,
                    "detected_at": r.detected_at.isoformat(),
                    "job_id": r.job_id,
                },
            )
            for r in rows
        ]
    )
