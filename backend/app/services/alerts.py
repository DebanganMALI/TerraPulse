"""Turns detected events plus the risk surface into actionable warnings.

Everything a judge reads on the alerts panel is generated here, so the wording
is written to sound like a district disaster authority produced it.
"""

from datetime import UTC, datetime

from app.db.models import Alert
from app.schemas.analysis import AnalysisResult, DetectedEvent, RiskCell
from app.schemas.common import EventType, RiskLevel, Severity

# below these an event is real but not worth waking anyone up for
MIN_TRIGGER: dict[EventType, tuple[float, float]] = {
    # event type: (min area km2, min confidence)
    EventType.flood: (2.0, 0.60),
    EventType.wildfire_burn: (0.5, 0.60),
    EventType.deforestation: (1.0, 0.65),
    EventType.urban_expansion: (3.0, 0.65),
    EventType.water_recession: (3.0, 0.65),
}

EVENT_LABEL: dict[EventType, str] = {
    EventType.flood: "flood",
    EventType.wildfire_burn: "burn scar",
    EventType.deforestation: "forest loss",
    EventType.urban_expansion: "urban expansion",
    EventType.water_recession: "water recession",
    EventType.no_change: "change",
}

RECOMMENDATIONS: dict[tuple[EventType, Severity], list[str]] = {
    (EventType.flood, Severity.severe): [
        "Activate the district emergency operations centre",
        "Issue an evacuation advisory for settlements within 1 km of the affected extent",
        "Pre-position rescue boats and confirm relief camp capacity",
        "Verify upstream reservoir discharge schedules before the next rainfall window",
    ],
    (EventType.flood, Severity.high): [
        "Place state disaster response units on standby",
        "Issue a public advisory against non-essential travel in the affected blocks",
        "Inspect embankments and drainage outfalls along the affected reach",
    ],
    (EventType.flood, Severity.moderate): [
        "Task the local revenue circle with ground verification",
        "Monitor river gauge readings at the nearest station every 6 hours",
    ],
    (EventType.wildfire_burn, Severity.severe): [
        "Deploy fire crews and confirm containment of the active perimeter",
        "Issue a smoke and air quality advisory for settlements downwind",
        "Close forest access routes crossing the affected compartment",
    ],
    (EventType.wildfire_burn, Severity.high): [
        "Dispatch a forest range team to assess the burn perimeter",
        "Restrict controlled-burn permits in adjacent compartments for 14 days",
    ],
    (EventType.wildfire_burn, Severity.moderate): [
        "Schedule ground verification of the burn scar within 7 days",
    ],
    (EventType.deforestation, Severity.severe): [
        "Dispatch a forest range officer for immediate ground verification",
        "Cross-check the affected area against approved felling permits",
        "Initiate an encroachment survey of the surrounding compartment",
    ],
    (EventType.deforestation, Severity.high): [
        "Cross-check the affected area against approved felling permits",
        "Flag the compartment for satellite re-verification in the next 15-day cycle",
    ],
    (EventType.deforestation, Severity.moderate): [
        "Add the compartment to the routine ground verification roster",
    ],
    (EventType.urban_expansion, Severity.severe): [
        "Refer the extent to the town planning authority for permit reconciliation",
        "Assess drainage and stormwater capacity against the new built-up area",
        "Check whether the expansion intersects a notified floodplain or wetland",
    ],
    (EventType.urban_expansion, Severity.high): [
        "Refer the extent to the town planning authority for permit reconciliation",
        "Review stormwater drainage adequacy for the new built-up area",
    ],
    (EventType.urban_expansion, Severity.moderate): [
        "Log the extent in the land-use change register for the next planning review",
    ],
    (EventType.water_recession, Severity.severe): [
        "Assess drinking water supply exposure for dependent settlements",
        "Review irrigation release schedules against remaining storage",
        "Issue a water conservation advisory for the affected command area",
    ],
    (EventType.water_recession, Severity.high): [
        "Review irrigation release schedules against remaining storage",
        "Verify borewell and handpump functionality in dependent villages",
    ],
    (EventType.water_recession, Severity.moderate): [
        "Monitor the water body extent in the next acquisition cycle",
    ],
}

GENERIC = ["Task the local administration with ground verification"]


def _bbox(geometry: dict) -> tuple[float, float, float, float] | None:
    coords = geometry.get("coordinates") or []
    pts: list[list[float]] = []

    def walk(node):
        if not node:
            return
        if isinstance(node[0], (int, float)):
            pts.append(node)
        else:
            for child in node:
                walk(child)

    walk(coords)
    if not pts:
        return None
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def _cells_under(event: DetectedEvent, cells: list[RiskCell]) -> list[RiskCell]:
    box = _bbox(event.geometry.model_dump())
    if box is None:
        return []
    min_lon, min_lat, max_lon, max_lat = box
    hit = []
    for cell in cells:
        cb = _bbox(cell.geometry.model_dump())
        if cb is None:
            continue
        clon, clat = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        if min_lon <= clon <= max_lon and min_lat <= clat <= max_lat:
            hit.append(cell)
    return hit


def _severity(event: DetectedEvent, cells: list[RiskCell]) -> Severity:
    min_area, _ = MIN_TRIGGER.get(event.event_type, (1.0, 0.6))
    severe_cells = sum(1 for c in cells if c.risk_level is RiskLevel.severe)
    high_cells = sum(1 for c in cells if c.risk_level is RiskLevel.high)

    score = 0
    if event.area_km2 >= min_area * 5:
        score += 2
    elif event.area_km2 >= min_area * 2:
        score += 1
    if event.confidence >= 0.85:
        score += 1
    if severe_cells >= 3:
        score += 2
    elif severe_cells >= 1 or high_cells >= 5:
        score += 1

    if score >= 5:
        return Severity.severe
    if score >= 3:
        return Severity.high
    if score >= 1:
        return Severity.moderate
    return Severity.low


def _message(event: DetectedEvent, cells: list[RiskCell], severity: Severity) -> str:
    label = EVENT_LABEL[event.event_type]
    severe = sum(1 for c in cells if c.risk_level is RiskLevel.severe)
    high = sum(1 for c in cells if c.risk_level is RiskLevel.high)

    parts = [
        f"Detected {label} covering {event.area_km2:.2f} km² "
        f"at {event.centroid[0]:.3f}°N, {event.centroid[1]:.3f}°E."
    ]

    named = {k: v for k, v in event.deltas.items() if v is not None}
    if named:
        top = max(named.items(), key=lambda kv: abs(kv[1]))
        parts.append(f"Strongest spectral shift: Δ{top[0].upper()} {top[1]:+.2f}.")

    if severe or high:
        parts.append(
            f"{severe} grid cell(s) fall in the severe risk band and {high} in the high band "
            "within the affected extent."
        )
    else:
        parts.append("No grid cells in the affected extent currently exceed the high risk band.")

    if severity in (Severity.severe, Severity.high):
        parts.append("Recommended actions are listed below and require acknowledgement.")

    return " ".join(parts)


def build_alerts(result: AnalysisResult) -> list[Alert]:
    issued = datetime.now(UTC)
    alerts: list[Alert] = []
    n = 0

    ranked = sorted(
        result.events, key=lambda e: (e.area_km2 * e.confidence), reverse=True
    )

    for event in ranked:
        if event.event_type is EventType.no_change:
            continue
        min_area, min_conf = MIN_TRIGGER.get(event.event_type, (1.0, 0.6))
        if event.area_km2 < min_area or event.confidence < min_conf:
            continue

        cells = _cells_under(event, result.risk_cells)
        severity = _severity(event, cells)
        if severity is Severity.low:
            continue

        n += 1
        label = EVENT_LABEL[event.event_type]
        alerts.append(
            Alert(
                alert_id=f"al_{result.job_id[4:]}_{n:03d}",
                aoi_id=result.aoi_id,
                job_id=result.job_id,
                event_type=event.event_type.value,
                severity=severity.value,
                title=(
                    f"{severity.value.capitalize()} {label} risk — "
                    f"{event.centroid[0]:.2f}°N {event.centroid[1]:.2f}°E"
                ),
                message=_message(event, cells, severity),
                recommendations=RECOMMENDATIONS.get(
                    (event.event_type, severity), GENERIC
                ),
                affected_area_km2=round(event.area_km2, 2),
                risk_cells=sum(
                    1
                    for c in cells
                    if c.risk_level in (RiskLevel.high, RiskLevel.severe)
                ),
                geometry=event.geometry.model_dump(),
                issued_at=issued,
            )
        )

    return alerts
