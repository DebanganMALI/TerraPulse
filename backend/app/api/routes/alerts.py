from datetime import UTC, datetime

from fastapi import APIRouter, Path, Query, Request
from sqlalchemy import select

from app.db.models import Alert
from app.errors import AppError
from app.schemas.alerts import AlertOut
from app.schemas.common import (
    AOI_ID_PATTERN,
    SEVERITY_ORDER,
    ErrorCode,
    Geometry,
    Severity,
)
from app.security.deps import AuthorityUser, CurrentUser, DbDep
from app.services import audit

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _out(row: Alert) -> AlertOut:
    return AlertOut(
        alert_id=row.alert_id,
        aoi_id=row.aoi_id,
        event_type=row.event_type,
        severity=row.severity,
        title=row.title,
        message=row.message,
        recommendations=row.recommendations,
        affected_area_km2=row.affected_area_km2,
        risk_cells=row.risk_cells,
        geometry=Geometry.model_validate(row.geometry) if row.geometry else None,
        issued_at=row.issued_at,
        acknowledged=row.acknowledged,
        acknowledged_by=row.acknowledged_by,
        acknowledged_at=row.acknowledged_at,
    )


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: DbDep,
    user: CurrentUser,
    aoi_id: str = Query(pattern=AOI_ID_PATTERN),
    min_severity: Severity = Query(Severity.info),
) -> list[AlertOut]:
    keep = [
        s.value for s in Severity if SEVERITY_ORDER[s] >= SEVERITY_ORDER[min_severity]
    ]
    rows = db.scalars(
        select(Alert).where(Alert.aoi_id == aoi_id, Alert.severity.in_(keep))
    ).all()
    rows = sorted(
        rows,
        key=lambda r: (SEVERITY_ORDER[Severity(r.severity)], r.affected_area_km2),
        reverse=True,
    )
    return [_out(r) for r in rows]


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge(
    request: Request,
    db: DbDep,
    user: AuthorityUser,
    alert_id: str = Path(max_length=32),
) -> AlertOut:
    row = db.scalar(select(Alert).where(Alert.alert_id == alert_id))
    if row is None:
        raise AppError(404, ErrorCode.alert_not_found, f"unknown alert: {alert_id}")

    row.acknowledged = True
    row.acknowledged_by = user.username
    row.acknowledged_at = datetime.now(UTC)
    db.commit()

    audit.record(db, request, "alert_ack", username=user.username, target=alert_id)
    return _out(row)
