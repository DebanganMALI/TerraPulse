import json

import numpy as np
import rasterio

from app.config import settings
from app.pipeline.providers.base import SceneBundle
from app.security.paths import safe_join

# Sentinel-2 L2A digital numbers are reflectance x 10000
DN_SCALE = 10_000.0

DEFAULT_BANDS = {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5}


class LocalProvider:
    """Reads the before/after pair written by scripts/stack.py."""

    def load(self, aoi_id: str) -> SceneBundle:
        folder = safe_join(settings().scenes_dir, aoi_id)

        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        band_map = meta.get("band_map") or DEFAULT_BANDS

        arrays = {}
        profile = None
        for which in ("before", "after"):
            with rasterio.open(folder / f"{which}.tif") as src:
                arrays[which] = np.clip(src.read().astype("float32") / DN_SCALE, 0, 1.5)
                if profile is None:
                    profile = (src.transform, src.crs)

        transform, crs = profile
        return SceneBundle(
            before=arrays["before"],
            after=arrays["after"],
            transform=transform,
            crs=crs,
            band_map=band_map,
            meta=meta,
        )
