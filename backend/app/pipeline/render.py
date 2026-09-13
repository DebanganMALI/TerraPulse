import json
import logging
from pathlib import Path

import numpy as np
import rasterio.transform
from PIL import Image

from app.pipeline.providers.base import SceneBundle
from app.schemas.common import EventType

log = logging.getLogger("terrapulse")

STATIC = Path(__file__).resolve().parents[1] / "static" / "overlays"
MAX_EDGE = 1500

MASK_RGB = {
    EventType.flood: (47, 129, 247),
    EventType.deforestation: (219, 109, 40),
    EventType.wildfire_burn: (248, 81, 73),
    EventType.urban_expansion: (163, 113, 247),
    EventType.water_recession: (57, 197, 207),
    EventType.no_change: (110, 118, 129),
}


def _stretch(band: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(band, (2, 98))
    if hi <= lo:
        return np.zeros_like(band, dtype="uint8")
    return (np.clip((band - lo) / (hi - lo), 0, 1) * 255).astype("uint8")


def _downscale(img: Image.Image) -> Image.Image:
    if max(img.size) <= MAX_EDGE:
        return img
    scale = MAX_EDGE / max(img.size)
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def _true_colour(bundle: SceneBundle, which: str) -> Image.Image:
    rgb = np.dstack(
        [_stretch(bundle.band(which, n)) for n in ("red", "green", "blue")]
    )
    return _downscale(Image.fromarray(rgb, mode="RGB"))


def render_all(
    bundle: SceneBundle, mask: np.ndarray, aoi_id: str
) -> dict[str, str]:
    out_dir = STATIC / aoi_id
    out_dir.mkdir(parents=True, exist_ok=True)

    h, w = bundle.before.shape[1], bundle.before.shape[2]
    west, south, east, north = rasterio.transform.array_bounds(h, w, bundle.transform)
    # array_bounds returns (left, bottom, right, top)
    (out_dir / "bounds.json").write_text(
        json.dumps({"bbox": [west, south, east, north]}), encoding="utf-8"
    )

    written: dict[str, str] = {}
    try:
        for which in ("before", "after"):
            _true_colour(bundle, which).save(out_dir / f"{which}.png", optimize=True)
            written[which] = f"/static/overlays/{aoi_id}/{which}.png"

        rgba = np.zeros((*mask.shape, 4), dtype="uint8")
        rgba[mask] = (*MASK_RGB[EventType.flood], 170)
        _downscale(Image.fromarray(rgba, mode="RGBA")).save(
            out_dir / "change_mask.png", optimize=True
        )
        written["change_mask"] = f"/static/overlays/{aoi_id}/change_mask.png"
    except Exception as exc:
        log.warning("overlay rendering failed for %s: %s", aoi_id, exc)

    return written
