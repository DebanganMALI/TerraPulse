from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from app.config import settings
from app.security.paths import safe_join

from .base import SceneBundle

# Two different scalings turn up depending on where the GeoTIFF came from:
# a raw L2A product stores reflectance * 10000, while Sentinel Hub's 16-bit
# export stores reflectance * 65535. Guessing wrong silently flattens every
# bright pixel and makes all four index thresholds meaningless, so detect it
# from the data and let meta.json override with "reflectance_scale".
SCALE_L2A = 10000.0
SCALE_SH16 = 65535.0
SCALE_SWITCH = 20000.0

DEFAULT_BAND_MAP = {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5}


def scene_dir(aoi_id: str) -> Path:
    return safe_join(settings().scenes_dir, aoi_id)


def read_meta(aoi_id: str) -> dict:
    path = safe_join(scene_dir(aoi_id), "meta.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_raw(path: Path):
    with rasterio.open(path) as src:
        return src.read().astype("float32"), src.transform, src.crs


def reflectance_scale(meta: dict, *arrays: np.ndarray) -> float:
    override = meta.get("reflectance_scale")
    if override:
        return float(override)
    peak = max(float(np.nanmax(a)) for a in arrays)
    if peak <= 1.5:
        return 1.0
    return SCALE_SH16 if peak > SCALE_SWITCH else SCALE_L2A


class LocalProvider:
    def load(self, aoi_id: str) -> SceneBundle:
        meta = read_meta(aoi_id)
        d = scene_dir(aoi_id)

        before, bt, bcrs = _read_raw(safe_join(d, "before.tif"))
        after, at, acrs = _read_raw(safe_join(d, "after.tif"))

        # one scale for both scenes: a per-scene guess could differ and would
        # make the deltas nonsense
        scale = reflectance_scale(meta, before, after)
        for arr in (before, after):
            arr /= scale
            np.clip(arr, 0.0, 1.0, out=arr)

        same_grid = (
            bcrs == acrs
            and bt.almost_equals(at)
            and before.shape[1:] == after.shape[1:]
        )

        return SceneBundle(
            before=before,
            after=after,
            transform=bt,
            crs=bcrs,
            band_map=meta.get("band_map") or DEFAULT_BAND_MAP,
            meta={**meta, "reflectance_scale": scale},
            after_transform=None if same_grid else at,
            after_crs=None if same_grid else acrs,
        )
