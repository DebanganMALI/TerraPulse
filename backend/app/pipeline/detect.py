from __future__ import annotations

import numpy as np
from scipy import ndimage

from .indices import INDEX_NAMES

# Thresholds apply to the SCENE-NORMALISED delta (see normalise_deltas), not the
# raw one. Empirical, tuned against the Kerala and Bandipur pairs.
THRESHOLDS = {"ndwi": 0.20, "ndvi": 0.25, "nbr": 0.30, "ndbi": 0.30}

# blue reflectance above this in L2A is nearly always cloud
CLOUD_BLUE = 0.25

# Cloud shadow reads as a large negative brightness step and gets detected as
# new water. It sits next to its cloud, so dilating the cloud mask removes most
# of it without needing a separate shadow classifier. 30 px at 10 m ~ 300 m.
CLOUD_DILATION_PX = 30

# NDWI above this in BOTH scenes is sea, lake or river that was already there.
# Flood is *new* water, so permanent water is excluded rather than detected.
PERMANENT_WATER_NDWI = 0.30

OPENING_ITERATIONS = 2


def cloud_mask(arr: np.ndarray, band_map: dict[str, int]) -> np.ndarray | None:
    i = band_map.get("blue")
    if i is None or i > arr.shape[0]:
        return None
    return arr[i - 1] > CLOUD_BLUE


def valid_mask(
    before: np.ndarray,
    after: np.ndarray,
    band_map: dict[str, int],
    before_idx: dict,
    after_idx: dict,
) -> tuple[np.ndarray, dict[str, float]]:
    """Pixels where a change measurement means anything.

    Excluded: cloud in either scene, nodata at the granule edge, and water that
    was already present in both. Without this the sea alone becomes one enormous
    false 'change' region and swamps everything else.
    """
    shape = before.shape[-2:]
    cloud = np.zeros(shape, bool)
    for arr in (before, after):
        c = cloud_mask(arr, band_map)
        if c is not None:
            cloud |= c
    if cloud.any():
        cloud = ndimage.binary_dilation(cloud, iterations=CLOUD_DILATION_PX)

    nodata = (before.min(axis=0) <= 0) | (after.min(axis=0) <= 0)

    bw, aw = before_idx.get("ndwi"), after_idx.get("ndwi")
    if bw is None or aw is None:
        permanent = np.zeros(shape, bool)
    else:
        permanent = (bw > PERMANENT_WATER_NDWI) & (aw > PERMANENT_WATER_NDWI)

    valid = ~(cloud | nodata | permanent)
    stats = {
        "cloud": float(cloud.mean()),
        "nodata": float(nodata.mean()),
        "permanent_water": float(permanent.mean()),
        "valid": float(valid.mean()),
    }
    return valid, stats


def deltas_of(before_idx: dict, after_idx: dict) -> dict[str, np.ndarray | None]:
    out: dict[str, np.ndarray | None] = {}
    for k in INDEX_NAMES:
        b, a = before_idx.get(k), after_idx.get(k)
        out[k] = None if b is None or a is None else (a - b)
    return out


def normalise_deltas(
    deltas: dict[str, np.ndarray | None], valid: np.ndarray | None
) -> tuple[dict[str, np.ndarray | None], dict[str, float]]:
    """Remove the scene-wide component of each delta.

    A dry-season baseline against a monsoon scene shifts every index across the
    whole image - on our Kerala pair the median NDWI delta was +0.19 before any
    real change was considered. Subtracting the median leaves relative change,
    which is what the thresholds are meant to measure. Standard relative
    radiometric normalisation; the offsets are reported so the shift is visible
    rather than hidden.
    """
    out: dict[str, np.ndarray | None] = {}
    offsets: dict[str, float] = {}
    for k, d in deltas.items():
        if d is None:
            out[k] = None
            continue
        sample = d[valid] if valid is not None and valid.any() else d
        offset = float(np.median(sample))
        offsets[k] = round(offset, 4)
        out[k] = d - offset
    return out, offsets


def detect_change(
    before_idx: dict,
    after_idx: dict,
    valid: np.ndarray | None = None,
    thresholds: dict[str, float] | None = None,
    normalise: bool = True,
) -> tuple[np.ndarray, dict[str, np.ndarray | None], dict[str, float]]:
    t = {**THRESHOLDS, **(thresholds or {})}
    raw = deltas_of(before_idx, after_idx)

    grids = [d for d in raw.values() if d is not None]
    if not grids:
        raise ValueError("no usable index pairs")

    tested, offsets = normalise_deltas(raw, valid) if normalise else (raw, {})

    mask = np.zeros(grids[0].shape, dtype=bool)
    for k, d in tested.items():
        if d is not None:
            mask |= np.abs(d) > t[k]

    if valid is not None:
        mask &= valid

    mask = ndimage.binary_opening(mask, iterations=OPENING_ITERATIONS)
    # raw deltas are what the popup shows: they are the physical measurement
    return mask.astype("uint8"), raw, offsets


def delta_range(deltas: dict[str, np.ndarray | None]) -> dict[str, tuple[float, float]]:
    return {
        k: (float(np.min(d)), float(np.max(d)))
        for k, d in deltas.items()
        if d is not None
    }
