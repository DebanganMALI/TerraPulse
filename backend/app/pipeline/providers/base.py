from __future__ import annotations

from typing import NamedTuple, Protocol

import numpy as np
from affine import Affine
from rasterio.crs import CRS


class SceneBundle(NamedTuple):
    before: np.ndarray                      # (bands, h, w) float32, reflectance 0..1
    after: np.ndarray
    transform: Affine                       # the before-scene grid until align() runs
    crs: CRS
    band_map: dict[str, int]                # 1-based, matching rasterio band numbering
    meta: dict
    # set only when the after scene sits on a different grid; align() consumes these
    # and returns a bundle with both back to None
    after_transform: Affine | None = None
    after_crs: CRS | None = None

    @property
    def aligned(self) -> bool:
        return self.after_transform is None and self.after_crs is None


class ImageryProvider(Protocol):
    def load(self, aoi_id: str) -> SceneBundle: ...
