import numpy as np
from scipy import ndimage

# Empirical, tuned against Sentinel-2 L2A. These are the numbers to adjust when
# a scene under- or over-detects; everything downstream follows from them.
THRESHOLDS = {
    "ndwi": 0.15,  # below this is seasonal wetness, not flooding
    "ndvi": 0.20,  # below this is normal phenology
    "nbr": 0.25,  # standard dNBR low-severity burn boundary
    "ndbi": 0.10,  # construction signal is subtle
}


def deltas_of(
    before: dict[str, np.ndarray], after: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    return {k: (after[k] - before[k]).astype("float32") for k in before}


def detect_change(
    deltas: dict[str, np.ndarray],
    exclude: np.ndarray | None = None,
    denoise_iterations: int = 2,
) -> np.ndarray:
    shape = next(iter(deltas.values())).shape
    mask = np.zeros(shape, dtype=bool)
    for key, limit in THRESHOLDS.items():
        if key in deltas:
            mask |= np.abs(deltas[key]) > limit

    if exclude is not None:
        mask &= ~exclude

    if denoise_iterations:
        mask = ndimage.binary_opening(mask, iterations=denoise_iterations)
        mask = ndimage.binary_closing(mask, iterations=1)
    return mask
