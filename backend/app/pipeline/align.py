from __future__ import annotations

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import array_bounds, from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds

from .providers.base import SceneBundle

TARGET_CRS = CRS.from_epsg(4326)

# keeps a full run to a few seconds; finer than this buys nothing at demo zoom
MAX_EDGE = 2400


def _bounds_4326(transform, crs, shape) -> tuple[float, float, float, float]:
    h, w = shape[-2:]
    left, bottom, right, top = array_bounds(h, w, transform)
    return transform_bounds(crs, TARGET_CRS, left, bottom, right, top)


def _warp(src, src_transform, src_crs, dst_transform, dst_shape) -> np.ndarray:
    dst = np.zeros((src.shape[0], *dst_shape), dtype="float32")
    reproject(
        source=src,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=TARGET_CRS,
        resampling=Resampling.bilinear,
    )
    return dst


def align(bundle: SceneBundle) -> SceneBundle:
    if bundle.aligned and bundle.crs == TARGET_CRS:
        return bundle

    at = bundle.after_transform or bundle.transform
    acrs = bundle.after_crs or bundle.crs

    bb = _bounds_4326(bundle.transform, bundle.crs, bundle.before.shape)
    ab = _bounds_4326(at, acrs, bundle.after.shape)

    left, bottom = max(bb[0], ab[0]), max(bb[1], ab[1])
    right, top = min(bb[2], ab[2]), min(bb[3], ab[3])
    if right <= left or top <= bottom:
        raise ValueError("before and after scenes do not overlap")

    bh, bw = bundle.before.shape[-2:]
    res = max((bb[2] - bb[0]) / bw, (bb[3] - bb[1]) / bh)

    w = max(int(round((right - left) / res)), 1)
    h = max(int(round((top - bottom) / res)), 1)
    if max(w, h) > MAX_EDGE:
        k = MAX_EDGE / max(w, h)
        w, h = max(int(w * k), 1), max(int(h * k), 1)

    dst_transform = from_bounds(left, bottom, right, top, w, h)

    return bundle._replace(
        before=_warp(bundle.before, bundle.transform, bundle.crs, dst_transform, (h, w)),
        after=_warp(bundle.after, at, acrs, dst_transform, (h, w)),
        transform=dst_transform,
        crs=TARGET_CRS,
        after_transform=None,
        after_crs=None,
    )


def bbox_of(bundle: SceneBundle) -> list[float]:
    h, w = bundle.before.shape[-2:]
    return list(array_bounds(h, w, bundle.transform))
