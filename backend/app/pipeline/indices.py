from __future__ import annotations

import numpy as np

EPS = 1e-6

INDEX_NAMES = ("ndwi", "ndvi", "nbr", "ndbi")


def _norm(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # EPS stops nodata/edge pixels (both bands zero) becoming nan, and one nan
    # propagates through the entire change mask
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (a - b) / (a + b + EPS)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype("float32")


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _norm(green, nir)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return _norm(nir, red)


def nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return _norm(nir, swir)


def ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return _norm(swir, nir)


def compute(arr: np.ndarray, band_map: dict[str, int]) -> dict[str, np.ndarray | None]:
    def band(name: str) -> np.ndarray | None:
        i = band_map.get(name)
        if i is None or i > arr.shape[0]:
            return None
        return arr[i - 1]

    green, red, nir, swir = band("green"), band("red"), band("nir"), band("swir")

    out: dict[str, np.ndarray | None] = dict.fromkeys(INDEX_NAMES)
    if green is not None and nir is not None:
        out["ndwi"] = ndwi(green, nir)
    if nir is not None and red is not None:
        out["ndvi"] = ndvi(nir, red)
    if nir is not None and swir is not None:
        out["nbr"] = nbr(nir, swir)
        out["ndbi"] = ndbi(swir, nir)
    return out
