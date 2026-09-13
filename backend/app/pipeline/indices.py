import numpy as np

from app.pipeline.providers.base import SceneBundle

EPS = 1e-6


def _norm(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (a - b) / (a + b + EPS)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype("float32")


def compute(bundle: SceneBundle, which: str) -> dict[str, np.ndarray]:
    b = lambda name: bundle.band(which, name)  # noqa: E731
    green, red, nir, swir = b("green"), b("red"), b("nir"), b("swir")
    return {
        "ndwi": _norm(green, nir),  # water:      higher = wetter
        "ndvi": _norm(nir, red),  # vegetation: higher = greener
        "nbr": _norm(nir, swir),  # burn:       drops sharply after fire
        "ndbi": _norm(swir, nir),  # built-up:   higher = more impervious
    }


def cloud_mask(bundle: SceneBundle, which: str, threshold: float = 0.25) -> np.ndarray:
    """Cheap brightness test. Not a real cloud classifier - it just keeps bright
    cloud tops from being reported as change, and the excluded fraction goes
    into result.warnings so the limitation is stated rather than hidden."""
    return bundle.band(which, "blue") > threshold
