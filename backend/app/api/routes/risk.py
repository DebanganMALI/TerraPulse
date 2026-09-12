from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.db.models import Alert, Event, Job, RiskCell
from app.schemas.common import (
    AOI_ID_PATTERN,
    RISK_LEVEL_ORDER,
    Feature,
    FeatureCollection,
    Geometry,
    RiskLevel,
)
from app.schemas.risk import StatsOut
from app.security.deps import CurrentUser, DbDep

router = APIRouter(tags=["results"])


@router.get("/risk", response_model=FeatureCollection)
def risk(
    db: DbDep,
    user: CurrentUser,
    aoi_id: str = Query(pattern=AOI_ID_PATTERN),
    min_level: RiskLevel = Query(RiskLevel.low),
) -> FeatureCollection:
    keep = [
        level.value
        for level in RiskLevel
        if RISK_LEVEL_ORDER[level] >= RISK_LEVEL_ORDER[min_level]
    ]
    rows = db.scalars(
        select(RiskCell)
        .where(RiskCell.aoi_id == aoi_id, RiskCell.risk_level.in_(keep))
        .order_by(RiskCell.cell_id)
    ).all()

    return FeatureCollection(
        features=[
            Feature(
                geometry=Geometry.model_validate(r.geometry),
                properties={
                    "cell_id": r.cell_id,
                    "aoi_id": r.aoi_id,
                    "risk_score": r.risk_score,
                    "risk_level": r.risk_level,
                    "primary_risk": r.primary_risk,
                    "drivers": r.drivers,
                },
            )
            for r in rows
        ]
    )


@router.get("/stats", response_model=StatsOut)
def stats(
    db: DbDep, user: CurrentUser, aoi_id: str = Query(pattern=AOI_ID_PATTERN)
) -> StatsOut:
    by_type = dict(
        db.execute(
            select(Event.event_type, func.count())
            .where(Event.aoi_id == aoi_id)
            .group_by(Event.event_type)
        ).all()
    )
    by_level = dict(
        db.execute(
            select(RiskCell.risk_level, func.count())
            .where(RiskCell.aoi_id == aoi_id)
            .group_by(RiskCell.risk_level)
        ).all()
    )
    last = db.scalar(
        select(Job)
        .where(Job.aoi_id == aoi_id, Job.status == "done")
        .order_by(Job.finished_at.desc())
    )

    return StatsOut(
        aoi_id=aoi_id,
        total_events=sum(by_type.values()),
        total_changed_area_km2=round(
            db.scalar(
                select(func.coalesce(func.sum(Event.area_km2), 0.0)).where(
                    Event.aoi_id == aoi_id
                )
            ),
            2,
        ),
        by_event_type=by_type,
        risk_distribution={level.value: by_level.get(level.value, 0) for level in RiskLevel},
        highest_risk_score=round(
            db.scalar(
                select(func.coalesce(func.max(RiskCell.risk_score), 0.0)).where(
                    RiskCell.aoi_id == aoi_id
                )
            ),
            4,
        ),
        open_alerts=db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.aoi_id == aoi_id, Alert.acknowledged.is_(False))
        ),
        last_analysis_at=last.finished_at.isoformat() if last and last.finished_at else None,
    )
