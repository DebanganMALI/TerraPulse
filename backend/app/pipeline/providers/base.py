from typing import NamedTuple, Protocol

import numpy as np
from rasterio.crs import CRS
from rasterio.transform import Affine


class SceneBundle(NamedTuple):
    before: np.ndarray  # (bands, h, w) float32, reflectance 0..1
    after: np.ndarray
    transform: Affine
    crs: CRS
    band_map: dict[str, int]  # name -> 1-based band index
    meta: dict

    def band(self, which: str, name: str) -> np.ndarray:
        idx = self.band_map[name] - 1
        return (self.before if which == "before" else self.after)[idx]


class ImageryProvider(Protocol):
    def load(self, aoi_id: str) -> SceneBundle: ...
