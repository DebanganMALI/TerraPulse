"""Forward risk per grid cell.

This is a risk-propensity model over terrain, recent change and rainfall - not
a physical forecast. Say that plainly when asked; overclaiming here is what
sinks projects at judging.
"""

import csv
import logging
import math
from functools import lru_cache

import numpy as np
import rasterio.transform

from app.config import settings
from app.pipeline.vectorize import Region
from app.schemas.analysis import RiskCell, RiskDriver
from app.schemas.common import EventType, Geometry, risk_level_for

log = logging.getLogger("terrapulse")

GRID = 40  # 1600 cells - inside the 2500 map budget, smooth on screen

CELL_FEATURES = [
    "mean_d_ndwi",
    "mean_d_ndvi",
    "mean_d_nbr",
    "mean_d_ndbi",
    "changed_fraction",
    "dist_to_event_km",
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "before_ndvi",
    "before_ndbi",
]

DRIVER_LABEL = {
    "mean_d_ndwi": "water_extent_change",
    "mean_d_ndvi": "vegetation_loss",
    "mean_d_nbr": "burn_signal",
    "mean_d_ndbi": "built_up_change",
    "changed_fraction": "detected_change_density",
    "dist_to_event_km": "distance_to_water_change",
    "rainfall_7d_mm": "cumulative_rainfall_7d",
    "rainfall_30d_mm": "cumulative_rainfall_30d",
    "before_ndvi": "vegetation_cover",
    "before_ndbi": "built_up_exposure",
}


@lru_cache(maxsize=8)
def load_env(aoi_id: str) -> tuple[float, float, float]:
    """(rainfall_7d, rainfall_30d, temp_max) from data/env/<aoi_id>.csv.
    Missing file is fine - the model just loses those features."""
    path = settings().env_dir / f"{aoi_id}.csv"
    if not path.is_file():
        return 0.0, 0.0, 0.0
    try:
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        rain = [float(r.get("rainfall_mm") or 0) for r in rows]
        temp = [float(r.get("temp_max_c") or 0) for r in rows]
        return (
            sum(rain[-7:]),
            sum(rain[-30:]),
            max(temp) if temp else 0.0,
        )
    except (ValueError, OSError) as exc:
        log.warning("could not read env csv for %s: %s", aoi_id, exc)
        return 0.0, 0.0, 0.0


def _heuristic_score(f: dict[str, float]) -> float:
    """Used until a trained risk model exists. Deliberately simple and monotone
    so the map reads sensibly rather than randomly."""
    proximity = math.exp(-((f["dist_to_event_km"] / 6.0) ** 2))
    wetness = max(0.0, f["mean_d_ndwi"]) * 2.0
    density = f["changed_fraction"]
    rain = min(1.0, f["rainfall_7d_mm"] / 300.0)
    raw = 0.45 * proximity + 0.20 * wetness + 0.20 * density + 0.15 * rain
    return float(np.clip(raw, 0.0, 1.0))


def _drivers(f: dict[str, float]) -> list[RiskDriver]:
    weights = {
        "dist_to_event_km": 0.45 * math.exp(-((f["dist_to_event_km"] / 6.0) ** 2)),
        "rainfall_7d_mm": 0.15 * min(1.0, f["rainfall_7d_mm"] / 300.0),
        "mean_d_ndwi": 0.20 * max(0.0, f["mean_d_ndwi"]) * 2.0,
        "changed_fraction": 0.20 * f["changed_fraction"],
        "before_ndvi": 0.10 * max(0.0, f["before_ndvi"]),
    }
    total = sum(weights.values()) or 1.0
    top = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return [
        RiskDriver(
            name=DRIVER_LABEL.get(k, k),
            contribution=round(float(np.clip(v / total, 0.0, 1.0)), 3),
        )
        for k, v in top
    ]


def score_grid(
    shape: tuple[int, int],
    transform,
    deltas: dict[str, np.ndarray],
    before_idx: dict[str, np.ndarray],
    mask: np.ndarray,
    regions: list[Region],
    labels: list,
    aoi_id: str,
) -> list[RiskCell]:
    h, w = shape
    rain7, rain30, _temp = load_env(aoi_id)

    flood_points = [
        r.centroid
        for r, (etype, _) in zip(regions, labels, strict=False)
        if etype in (EventType.flood, EventType.water_recession)
    ] or [r.centroid for r in regions]

    step_r, step_c = max(1, h // GRID), max(1, w // GRID)
    cells: list[RiskCell] = []

    for gi in range(GRID):
        r0, r1 = gi * step_r, min(h, (gi + 1) * step_r)
        if r0 >= r1:
            continue
        for gj in range(GRID):
            c0, c1 = gj * step_c, min(w, (gj + 1) * step_c)
            if c0 >= c1:
                continue

            west, north = rasterio.transform.xy(transform, r0, c0, offset="ul")
            east, south = rasterio.transform.xy(transform, r1, c1, offset="ul")
            clat, clon = (north + south) / 2, (west + east) / 2

            if flood_points:
                nearest_deg = min(
                    math.hypot(clat - la, clon - lo) for la, lo in flood_points
                )
            else:
                nearest_deg = 1.0

            block = (slice(r0, r1), slice(c0, c1))
            f = {
                "mean_d_ndwi": float(deltas["ndwi"][block].mean()),
                "mean_d_ndvi": float(deltas["ndvi"][block].mean()),
                "mean_d_nbr": float(deltas["nbr"][block].mean()),
                "mean_d_ndbi": float(deltas["ndbi"][block].mean()),
                "changed_fraction": float(mask[block].mean()),
                "dist_to_event_km": nearest_deg * 110.574,
                "rainfall_7d_mm": rain7,
                "rainfall_30d_mm": rain30,
                "before_ndvi": float(before_idx["ndvi"][block].mean()),
                "before_ndbi": float(before_idx["ndbi"][block].mean()),
            }

            score = round(_heuristic_score(f), 4)
            ring = [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
            cells.append(
                RiskCell(
                    cell_id=f"c_{gi:04d}_{gj:04d}",
                    risk_score=score,
                    risk_level=risk_level_for(score),
                    primary_risk=EventType.flood,
                    geometry=Geometry(type="Polygon", coordinates=[ring]),
                    drivers=_drivers(f),
                )
            )
    return cells
