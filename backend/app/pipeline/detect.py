from __future__ import annotations

import numpy as np
from scipy import ndimage

from .indices import INDEX_NAMES

# Empirical, tuned against our scene pairs. NDWI 0.15 sits above seasonal wetness but
# below real inundation; NDVI 0.20 above normal phenology; NBR 0.25 is the conventional
# dNBR low-severity burn boundary; NDBI is lower because construction is a subtle signal.
THRESHOLDS = {"ndwi": 0.15, "ndvi": 0.20, "nbr": 0.25, "ndbi": 0.10}

# blue reflectance above this in L2A is nearly always cloud
CLOUD_BLUE = 0.25


def cloud_mask(arr: np.ndarray, band_map: dict[str, int]) -> np.ndarray | None:
    i = band_map.get("blue")
    if i is None or i > arr.shape[0]:
        return None
    return arr[i - 1] > CLOUD_BLUE


def deltas_of(before_idx: dict, after_idx: dict) -> dict[str, np.ndarray | None]:
    out: dict[str, np.ndarray | None] = {}
    for k in INDEX_NAMES:
        b, a = before_idx.get(k), after_idx.get(k)
        out[k] = None if b is None or a is None else (a - b)
    return out


def detect_change(
    before_idx: dict,
    after_idx: dict,
    exclude: np.ndarray | None = None,
    thresholds: dict[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray | None]]:
    t = {**THRESHOLDS, **(thresholds or {})}
    deltas = deltas_of(before_idx, after_idx)

    grids = [d for d in deltas.values() if d is not None]
    if not grids:
        raise ValueError("no usable index pairs")

    mask = np.zeros(grids[0].shape, dtype=bool)
    for k, d in deltas.items():
        if d is not None:
            mask |= np.abs(d) > t[k]

    if exclude is not None:
        mask &= ~exclude

    mask = ndimage.binary_opening(mask, iterations=2)
    return mask.astype("uint8"), deltas


def delta_range(deltas: dict[str, np.ndarray | None]) -> dict[str, tuple[float, float]]:
    return {
        k: (float(np.min(d)), float(np.max(d)))
        for k, d in deltas.items()
        if d is not None
    }
