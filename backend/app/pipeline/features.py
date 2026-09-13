from __future__ import annotations

import math

from app.schemas.common import EventType

from .vectorize import Region

# Fixed order. Training and inference reading these in different orders is a
# silent failure that produces confident nonsense, so it lives in one place and
# is saved inside the model artifact.
FEATURES = [
    "d_ndwi",
    "d_ndvi",
    "d_nbr",
    "d_ndbi",
    "d_ndwi_std",
    "d_ndvi_std",
    "before_ndvi",
    "before_ndwi",
    "before_ndbi",
    "area_km2",
    "compactness",
    "elongation",
    "rectangularity",
    "solidity",
]


def _f(v: float | None) -> float:
    return 0.0 if v is None else float(v)


def rectangularity(poly) -> float:
    """Area over its minimum rotated bounding rectangle.

    A Kuttanad paddy polder is a bunded rectangle and scores near 1. Natural
    inundation follows terrain and scores lower. The spectral rules cannot tell
    those apart - both are new standing water - so this is the one feature that
    gives the model something the rules do not have.
    """
    try:
        rect = poly.minimum_rotated_rectangle
        return round(float(poly.area / rect.area), 4) if rect.area > 0 else 0.0
    except Exception:
        return 0.0


def solidity(poly) -> float:
    # area over convex hull: ragged, many-fingered extents score low
    try:
        hull = poly.convex_hull
        return round(float(poly.area / hull.area), 4) if hull.area > 0 else 0.0
    except Exception:
        return 0.0


def shape_metrics(poly) -> tuple[float, float]:
    # compactness and elongation carry real signal: floods follow valleys and are
    # elongated, urban expansion is blocky, deforestation patches are ragged
    area = poly.area
    perim = poly.length
    compactness = (4 * math.pi * area / (perim * perim)) if perim > 0 else 0.0
    min_lon, min_lat, max_lon, max_lat = poly.bounds
    w, h = max_lon - min_lon, max_lat - min_lat
    elongation = (max(w, h) / min(w, h)) if min(w, h) > 0 else 1.0
    return round(compactness, 4), round(min(elongation, 20.0), 4)


def row(region: Region) -> dict[str, float]:
    compactness, elongation = shape_metrics(region.geometry)
    return {
        "d_ndwi": _f(region.deltas.get("ndwi")),
        "d_ndvi": _f(region.deltas.get("ndvi")),
        "d_nbr": _f(region.deltas.get("nbr")),
        "d_ndbi": _f(region.deltas.get("ndbi")),
        "d_ndwi_std": _f(region.delta_std.get("ndwi")),
        "d_ndvi_std": _f(region.delta_std.get("ndvi")),
        "before_ndvi": _f(region.before.get("ndvi")),
        "before_ndwi": _f(region.before.get("ndwi")),
        "before_ndbi": _f(region.before.get("ndbi")),
        "area_km2": float(region.area_km2),
        "compactness": compactness,
        "elongation": elongation,
        "rectangularity": rectangularity(region.geometry),
        "solidity": solidity(region.geometry),
    }


def vector(region: Region) -> list[float]:
    r = row(region)
    return [r[name] for name in FEATURES]


def rule_label(f: dict[str, float]) -> EventType:
    """Weak-supervision labeller.

    Used two ways: to bootstrap training labels (hand-corrected afterwards), and
    as the runtime fallback when the trained model is missing. Keeping it in the
    repo is also the evidence of how the labels were made.
    """
    if f["d_ndwi"] > 0.15 and f["d_ndvi"] < -0.05:
        return EventType.flood
    if f["d_ndwi"] < -0.15:
        return EventType.water_recession
    if f["d_nbr"] < -0.25 and f["d_ndvi"] < -0.15:
        return EventType.wildfire_burn
    if f["d_ndvi"] < -0.20 and abs(f["d_ndbi"]) < 0.05:
        return EventType.deforestation
    if f["d_ndbi"] > 0.10 and f["d_ndvi"] < -0.10:
        return EventType.urban_expansion
    return EventType.no_change
