from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.transform import array_bounds

from app.schemas.analysis import DetectedEvent
from app.schemas.common import EventType

log = logging.getLogger("terrapulse.pipeline")

# browsers choke on very large ImageOverlays and nobody can see the difference
MAX_EDGE = 1500

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
URL_PREFIX = "/static/overlays"

EVENT_RGB = {
    EventType.flood: (47, 129, 247),
    EventType.deforestation: (219, 109, 40),
    EventType.wildfire_burn: (248, 81, 73),
    EventType.urban_expansion: (163, 113, 247),
    EventType.water_recession: (57, 197, 207),
    EventType.no_change: (110, 118, 129),
}


def _downscale(arr: np.ndarray) -> np.ndarray:
    h, w = arr.shape[:2]
    step = max(1, int(np.ceil(max(h, w) / MAX_EDGE)))
    return arr[::step, ::step]


def _stretch(band: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(band, (2, 98))
    if hi <= lo:
        hi = lo + 1e-6
    return np.clip((band - lo) / (hi - lo), 0, 1)


def true_colour(arr: np.ndarray, band_map: dict[str, int]) -> Image.Image:
    chans = []
    for name in ("red", "green", "blue"):
        i = band_map.get(name)
        band = arr[i - 1] if i and i <= arr.shape[0] else np.zeros(arr.shape[1:], "float32")
        chans.append(_stretch(band))
    rgb = np.stack(chans, axis=-1)
    return Image.fromarray((_downscale(rgb) * 255).astype("uint8"), mode="RGB")


def mask_overlay(mask: np.ndarray, events: list[DetectedEvent]) -> Image.Image:
    # single dominant colour: per-polygon colouring needs rasterisation and buys
    # little at demo zoom
    kind = events[0].event_type if events else EventType.no_change
    r, g, b = EVENT_RGB.get(kind, EVENT_RGB[EventType.no_change])

    small = _downscale(mask.astype("uint8"))
    h, w = small.shape
    rgba = np.zeros((h, w, 4), dtype="uint8")
    on = small > 0
    rgba[on] = (r, g, b, 190)
    return Image.fromarray(rgba, mode="RGBA")


def render_all(
    aoi_id: str,
    bundle,
    mask: np.ndarray,
    events: list[DetectedEvent],
    warnings: list[str] | None = None,
) -> dict[str, str]:
    out_dir = STATIC_ROOT / "overlays" / aoi_id
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        if warnings is not None:
            warnings.append(f"could not create overlay directory: {exc}")
        return {}

    h, w = bundle.before.shape[-2:]
    bbox = list(array_bounds(h, w, bundle.transform))

    overlays: dict[str, str] = {}
    jobs = [
        ("before", lambda: true_colour(bundle.before, bundle.band_map)),
        ("after", lambda: true_colour(bundle.after, bundle.band_map)),
        ("change_mask", lambda: mask_overlay(mask, events)),
    ]

    for name, make in jobs:
        try:
            img = make()
            img.save(out_dir / f"{name}.png", optimize=True)
            (out_dir / f"{name}.bounds.json").write_text(
                json.dumps({"bbox": bbox}), encoding="utf-8"
            )
            overlays[name] = f"{URL_PREFIX}/{aoi_id}/{name}.png"
        except Exception as exc:
            log.warning("overlay %s failed: %s", name, exc)
            if warnings is not None:
                warnings.append(f"overlay '{name}' failed: {type(exc).__name__}")

    try:
        (out_dir / "bounds.json").write_text(json.dumps({"bbox": bbox}), encoding="utf-8")
    except OSError:
        pass

    return overlays
