"""Schema-valid stand-in for Part B's pipeline.

Selected by PIPELINE_MODE=mock. Exists so the frontend can be built against
realistic data before the real pipeline lands. Output is deterministic.
"""

import json
import math
import random
import time
from collections.abc import Callable
from pathlib import Path

from app.config import settings
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResult,
    DetectedEvent,
    RiskCell,
    RiskDriver,
)
from app.schemas.common import EventType, Geometry, risk_level_for

FALLBACK_BBOX = [76.10, 9.80, 76.60, 10.30]  # Ernakulam / Periyar

GRID = 20

STAGES: list[tuple[int, str]] = [
    (12, "loading scenes"),
    (28, "aligning rasters"),
    (44, "computing indices"),
    (60, "detecting change"),
    (72, "vectorizing regions"),
    (84, "classifying regions"),
    (94, "scoring risk"),
    (100, "done"),
]

# (event type, centre as fraction of bbox, size fraction, confidence, deltas)
SEEDS: list[tuple[EventType, tuple[float, float], tuple[float, float], float, dict]] = [
    (EventType.flood, (0.28, 0.55), (0.14, 0.07), 0.93,
     {"ndwi": 0.41, "ndvi": -0.24, "nbr": -0.06, "ndbi": 0.01}),
    (EventType.flood, (0.46, 0.42), (0.10, 0.11), 0.88,
     {"ndwi": 0.34, "ndvi": -0.19, "nbr": -0.03, "ndbi": 0.02}),
    (EventType.flood, (0.62, 0.63), (0.08, 0.05), 0.76,
     {"ndwi": 0.27, "ndvi": -0.14, "nbr": -0.02, "ndbi": 0.00}),
    (EventType.water_recession, (0.80, 0.28), (0.07, 0.06), 0.71,
     {"ndwi": -0.22, "ndvi": 0.08, "nbr": 0.04, "ndbi": 0.03}),
    (EventType.urban_expansion, (0.36, 0.80), (0.06, 0.05), 0.82,
     {"ndwi": -0.03, "ndvi": -0.17, "nbr": 0.02, "ndbi": 0.19}),
    (EventType.deforestation, (0.70, 0.86), (0.09, 0.06), 0.79,
     {"ndwi": -0.02, "ndvi": -0.31, "nbr": -0.11, "ndbi": 0.03}),
]


def _bbox_for(aoi_id: str) -> list[float]:
    meta = settings().scenes_dir / aoi_id / "meta.json"
    try:
        data = json.loads(Path(meta).read_text())
        bbox = [float(x) for x in data["bbox"]]
        if len(bbox) == 4:
            return bbox
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return FALLBACK_BBOX


def _blob(cx: float, cy: float, rx: float, ry: float, rng: random.Random) -> Geometry:
    """Irregular closed ring so polygons don't look machine-drawn."""
    ring = []
    for i in range(14):
        t = 2 * math.pi * i / 14
        j = 0.75 + rng.random() * 0.5
        ring.append([cx + rx * j * math.cos(t), cy + ry * j * math.sin(t)])
    ring.append(ring[0])
    return Geometry(type="Polygon", coordinates=[ring])


def _area_km2(rx_deg: float, ry_deg: float, lat: float) -> float:
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(lat))
    return round(math.pi * (rx_deg * km_per_deg_lon) * (ry_deg * km_per_deg_lat), 2)


def _events(aoi_id: str, bbox: list[float], rng: random.Random) -> list[DetectedEvent]:
    min_lon, min_lat, max_lon, max_lat = bbox
    w, h = max_lon - min_lon, max_lat - min_lat
    out = []
    for etype, (fx, fy), (frx, fry), conf, deltas in SEEDS:
        cx, cy = min_lon + fx * w, min_lat + fy * h
        rx, ry = frx * w, fry * h
        out.append(
            DetectedEvent(
                event_type=etype,
                confidence=conf,
                area_km2=_area_km2(rx, ry, cy),
                centroid=(round(cy, 5), round(cx, 5)),
                geometry=_blob(cx, cy, rx, ry, rng),
                deltas=deltas,
            )
        )
    return out


def _risk_cells(bbox: list[float], events: list[DetectedEvent]) -> list[RiskCell]:
    min_lon, min_lat, max_lon, max_lat = bbox
    dx, dy = (max_lon - min_lon) / GRID, (max_lat - min_lat) / GRID

    floods = [e for e in events if e.event_type == EventType.flood] or events

    cells: list[RiskCell] = []
    for r in range(GRID):
        for c in range(GRID):
            lon0, lat0 = min_lon + c * dx, min_lat + r * dy
            clon, clat = lon0 + dx / 2, lat0 + dy / 2

            # inverse-distance falloff from the nearest flood centroid
            nearest = min(
                math.hypot(clat - e.centroid[0], clon - e.centroid[1]) for e in floods
            )
            span = max(max_lon - min_lon, max_lat - min_lat)
            score = max(0.0, min(1.0, math.exp(-((nearest / (0.22 * span)) ** 2))))
            score = round(score * 0.92 + 0.04, 4)

            ring = [
                [lon0, lat0],
                [lon0 + dx, lat0],
                [lon0 + dx, lat0 + dy],
                [lon0, lat0 + dy],
                [lon0, lat0],
            ]
            cells.append(
                RiskCell(
                    cell_id=f"c_{r:04d}_{c:04d}",
                    risk_score=score,
                    risk_level=risk_level_for(score),
                    primary_risk=EventType.flood,
                    geometry=Geometry(type="Polygon", coordinates=[ring]),
                    drivers=_drivers(score),
                )
            )
    return cells


def _drivers(score: float) -> list[RiskDriver]:
    if score >= 0.75:
        raw = [("cumulative_rainfall_7d", 0.44), ("distance_to_water_change", 0.31),
               ("terrain_slope", 0.14)]
    elif score >= 0.50:
        raw = [("distance_to_water_change", 0.38), ("cumulative_rainfall_7d", 0.29),
               ("elevation", 0.18)]
    elif score >= 0.25:
        raw = [("terrain_slope", 0.35), ("cumulative_rainfall_30d", 0.27),
               ("vegetation_cover", 0.20)]
    else:
        raw = [("elevation", 0.41), ("terrain_slope", 0.26), ("vegetation_cover", 0.16)]
    return [RiskDriver(name=n, contribution=v) for n, v in raw]


def run_analysis(
    req: AnalysisRequest,
    on_progress: Callable[[int, str], None] | None = None,
) -> AnalysisResult:
    rng = random.Random(f"{req.aoi_id}:{req.job_id}")
    bbox = _bbox_for(req.aoi_id)

    for pct, stage in STAGES:
        if on_progress:
            on_progress(pct, stage)
        time.sleep(settings().mock_stage_seconds)

    events = _events(req.aoi_id, bbox, rng)
    cells = _risk_cells(bbox, events)

    return AnalysisResult(
        aoi_id=req.aoi_id,
        job_id=req.job_id,
        events=events,
        risk_cells=cells,
        overlays={
            "before": f"/static/overlays/{req.aoi_id}/before.png",
            "after": f"/static/overlays/{req.aoi_id}/after.png",
            "change_mask": f"/static/overlays/{req.aoi_id}/change_mask.png",
        },
        model_info={"classifier": "mock", "risk_model": "mock", "accuracy": "n/a"},
        warnings=["synthetic result: PIPELINE_MODE is mock"],
    )
