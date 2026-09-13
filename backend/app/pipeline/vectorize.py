import math
from typing import NamedTuple

import numpy as np
import rasterio.features
import shapely.geometry
from rasterio.transform import Affine
from shapely.geometry.base import BaseGeometry

# ~50 m at this latitude. Invisible at demo zoom, cuts GeoJSON payloads by an
# order of magnitude, and keeps Leaflet responsive.
SIMPLIFY_DEG = 0.0005

MIN_AREA_KM2 = 0.25


class Region(NamedTuple):
    geometry: BaseGeometry
    area_km2: float
    centroid: tuple[float, float]  # (lat, lon) - opposite order to the geometry
    deltas: dict[str, float]
    before: dict[str, float]
    pixels: int


def area_km2(geom: BaseGeometry) -> float:
    lat = geom.centroid.y
    km_per_deg_lat = 110.574
    km_per_deg_lon = 111.320 * math.cos(math.radians(lat))
    return abs(geom.area) * km_per_deg_lat * km_per_deg_lon


def to_regions(
    mask: np.ndarray,
    transform: Affine,
    deltas: dict[str, np.ndarray],
    before_idx: dict[str, np.ndarray],
    min_area_km2: float = MIN_AREA_KM2,
) -> list[Region]:
    shapes = rasterio.features.shapes(
        mask.astype("uint8"), mask=mask, transform=transform
    )

    regions: list[Region] = []
    for shape_dict, value in shapes:
        if not value:
            continue
        poly = shapely.geometry.shape(shape_dict)
        if poly.is_empty:
            continue
        poly = poly.simplify(SIMPLIFY_DEG, preserve_topology=True)
        if poly.is_empty:
            continue

        km2 = area_km2(poly)
        if km2 < min_area_km2:
            continue

        cell = rasterio.features.geometry_mask(
            [shape_dict], out_shape=mask.shape, transform=transform, invert=True
        )
        n = int(cell.sum())
        if n == 0:
            continue

        regions.append(
            Region(
                geometry=poly,
                area_km2=round(km2, 2),
                centroid=(round(poly.centroid.y, 5), round(poly.centroid.x, 5)),
                deltas={k: float(np.mean(v[cell])) for k, v in deltas.items()},
                before={k: float(np.mean(v[cell])) for k, v in before_idx.items()},
                pixels=n,
            )
        )

    regions.sort(key=lambda r: r.area_km2, reverse=True)
    return regions
