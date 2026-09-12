from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Alert, Event, RiskCell
from app.schemas.analysis import AnalysisResult
from app.services.alerts import _cells_under, _severity, build_alerts


def persist(db: Session, result: AnalysisResult) -> dict[str, int]:
    """Replace the stored result for this AOI with the new run's output."""
    aoi = result.aoi_id
    db.execute(delete(Event).where(Event.aoi_id == aoi))
    db.execute(delete(RiskCell).where(RiskCell.aoi_id == aoi))
    db.execute(delete(Alert).where(Alert.aoi_id == aoi))

    now = datetime.now(UTC)

    for i, event in enumerate(result.events, start=1):
        cells = _cells_under(event, result.risk_cells)
        db.add(
            Event(
                event_id=f"ev_{aoi}_{i:03d}",
                aoi_id=aoi,
                job_id=result.job_id,
                event_type=event.event_type.value,
                confidence=event.confidence,
                severity=_severity(event, cells).value,
                area_km2=event.area_km2,
                centroid_lat=event.centroid[0],
                centroid_lon=event.centroid[1],
                geometry=event.geometry.model_dump(),
                deltas=event.deltas,
                detected_at=now,
            )
        )

    for cell in result.risk_cells:
        db.add(
            RiskCell(
                cell_id=cell.cell_id,
                aoi_id=aoi,
                job_id=result.job_id,
                risk_score=cell.risk_score,
                risk_level=cell.risk_level.value,
                primary_risk=cell.primary_risk.value,
                geometry=cell.geometry.model_dump(),
                drivers=[d.model_dump() for d in cell.drivers],
            )
        )

    alerts = build_alerts(result)
    for alert in alerts:
        db.add(alert)

    db.commit()
    return {
        "events": len(result.events),
        "risk_cells": len(result.risk_cells),
        "alerts": len(alerts),
    }
