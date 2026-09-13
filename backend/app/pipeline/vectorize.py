from __future__ import annotations

import json
import math
from typing import NamedTuple

import numpy as np
import rasterio.features
import shapely
from scipy import ndimage
from shapely.geometry import shape as to_shapely

from .indices import INDEX_NAMES

MIN_AREA_KM2 = 0.25

# ~50 m at these latitudes: invisible at demo zoom, cuts the GeoJSON payload by
# roughly an order of magnitude
SIMPLIFY_DEG = 0.0005

# Leaflet copes with a few hundred polygons, not a few thousand
MAX_REGIONS = 120


class Region(NamedTuple):
    geometry: object                        # shapely, EPSG:4326, coords are (lon, lat)
    area_km2: float
    deltas: dict[str, float | None]
    delta_std: dict[str, float | None]
    before: dict[str, float | None]


def area_km2(poly) -> float:
    lat = poly.centroid.y
    return poly.area * 110574.0 * (111320.0 * math.cos(math.radians(lat))) / 1e6


def geometry_dict(poly) -> dict:
    return json.loads(shapely.to_geojson(poly))


def centroid_lat_lon(poly) -> tuple[float, float]:
    # the contract wants (lat, lon) here while the geometry stays (lon, lat)
    c = poly.centroid
    return (round(c.y, 6), round(c.x, 6))


def _stat(fn, grid, labeled, labels):
    return fn(grid, labeled, labels)


def to_polygons(
    mask: np.ndarray,
    transform,
    deltas: dict[str, np.ndarray | None],
    before_idx: dict[str, np.ndarray | None] | None = None,
    min_area_km2: float = MIN_AREA_KM2,
    max_regions: int = MAX_REGIONS,
) -> list[Region]:
    labeled, n = ndimage.label(mask)
    if n == 0:
        return []

    labels = np.arange(1, n + 1)
    means = {k: _stat(ndimage.mean, d, labeled, labels) for k, d in deltas.items() if d is not None}
    stds = {
        k: _stat(ndimage.standard_deviation, d, labeled, labels)
        for k, d in deltas.items()
        if d is not None
    }
    befores = {
        k: _stat(ndimage.mean, d, labeled, labels)
        for k, d in (before_idx or {}).items()
        if d is not None
    }

    parts: dict[int, list] = {}
    for geom, value in rasterio.features.shapes(
        labeled.astype("int32"), mask=labeled > 0, transform=transform
    ):
        parts.setdefault(int(value), []).append(to_shapely(geom))

    out: list[Region] = []
    for v, geoms in parts.items():
        poly = geoms[0] if len(geoms) == 1 else shapely.union_all(geoms)
        poly = poly.simplify(SIMPLIFY_DEG)
        if poly.is_empty or not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue

        a = area_km2(poly)
        if a < min_area_km2:
            continue

        i = v - 1
        out.append(
            Region(
                geometry=poly,
                area_km2=round(a, 3),
                deltas={k: (float(means[k][i]) if k in means else None) for k in INDEX_NAMES},
                delta_std={k: (float(stds[k][i]) if k in stds else None) for k in INDEX_NAMES},
                before={k: (float(befores[k][i]) if k in befores else None) for k in INDEX_NAMES},
            )
        )

    out.sort(key=lambda r: r.area_km2, reverse=True)
    return out[:max_regions]
