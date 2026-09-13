import math

import numpy as np

from app.pipeline.vectorize import Region

# Fixed order. Training and inference must read features in the same order or
# the model produces confident nonsense - the saved artifact carries this list
# and classify.py asserts it matches.
FEATURES: list[str] = [
    "d_ndwi",
    "d_ndvi",
    "d_nbr",
    "d_ndbi",
    "before_ndwi",
    "before_ndvi",
    "before_ndbi",
    "area_km2",
    "compactness",
    "elongation",
]


def _compactness(region: Region) -> float:
    p = region.geometry.length
    return float(4 * math.pi * region.geometry.area / (p * p)) if p else 0.0


def _elongation(region: Region) -> float:
    minx, miny, maxx, maxy = region.geometry.bounds
    w, h = maxx - minx, maxy - miny
    return float(max(w, h) / min(w, h)) if min(w, h) > 0 else 1.0


def vector(region: Region) -> dict[str, float]:
    """Shape carries real signal: floods follow valleys and are elongated,
    urban expansion is blocky, forest loss is irregular."""
    return {
        "d_ndwi": region.deltas.get("ndwi", 0.0),
        "d_ndvi": region.deltas.get("ndvi", 0.0),
        "d_nbr": region.deltas.get("nbr", 0.0),
        "d_ndbi": region.deltas.get("ndbi", 0.0),
        "before_ndwi": region.before.get("ndwi", 0.0),
        "before_ndvi": region.before.get("ndvi", 0.0),
        "before_ndbi": region.before.get("ndbi", 0.0),
        "area_km2": region.area_km2,
        "compactness": _compactness(region),
        "elongation": _elongation(region),
    }


def matrix(regions: list[Region]) -> np.ndarray:
    return np.array(
        [[vector(r)[name] for name in FEATURES] for r in regions], dtype="float32"
    )
