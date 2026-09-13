from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import shapely
from rasterio.transform import array_bounds
from shapely.geometry import Point, box

from app.config import settings
from app.schemas.analysis import DetectedEvent, RiskCell, RiskDriver
from app.schemas.common import EventType, risk_level_for
from app.security.paths import safe_join

from .indices import INDEX_NAMES

log = logging.getLogger("terrapulse.pipeline")

# 40x40 = 1600 cells: inside the contract's 2500 cap, smooth on the map, and
# finer than this is invisible at demo zoom while making Leaflet stutter.
GRID = 40

MODEL_FILE = "risk_model.joblib"

CELL_FEATURES = [
    "mean_d_ndwi",
    "mean_d_ndvi",
    "changed_fraction",
    "dist_to_event_km",
    "before_ndwi",
    "before_ndvi",
    "before_ndbi",
    "rainfall_7d_mm",
    "rainfall_30d_mm",
    "temp_max_c",
]

# what C shows in the popup; the raw feature names read like debug output
DRIVER_NAMES = {
    "mean_d_ndwi": "water_index_change",
    "mean_d_ndvi": "vegetation_loss",
    "changed_fraction": "extent_of_detected_change",
    "dist_to_event_km": "proximity_to_detected_event",
    "before_ndwi": "pre_existing_water",
    "before_ndvi": "vegetation_cover",
    "before_ndbi": "built_up_exposure",
    "rainfall_7d_mm": "cumulative_rainfall_7d",
    "rainfall_30d_mm": "cumulative_rainfall_30d",
    "temp_max_c": "maximum_temperature",
}

# Transparent fallback used when no trained model is present. Weights are a
# stated prior, not a fitted result - say so rather than implying otherwise.
HEURISTIC_WEIGHTS = {
    "mean_d_ndwi": 0.28,
    "changed_fraction": 0.22,
    "dist_to_event_km": 0.18,
    "rainfall_7d_mm": 0.12,
    "before_ndwi": 0.08,
    "mean_d_ndvi": 0.07,
    "before_ndbi": 0.05,
}

# value that maps to 1.0 when normalising a feature into [0, 1]
NORMALISERS = {
    "mean_d_ndwi": 0.40,
    "mean_d_ndvi": 0.40,
    "changed_fraction": 0.50,
    "dist_to_event_km": 8.0,
    "before_ndwi": 0.50,
    "before_ndvi": 0.60,
    "before_ndbi": 0.40,
    "rainfall_7d_mm": 250.0,
    "rainfall_30d_mm": 900.0,
    "temp_max_c": 40.0,
}


def block_mean(a: np.ndarray, n: int = GRID) -> np.ndarray:
    h, w = a.shape
    bh, bw = max(h // n, 1), max(w // n, 1)
    a = a[: bh * n, : bw * n]
    return a.reshape(n, bh, n, bw).mean(axis=(1, 3))


def _km_per_deg(lat: float) -> tuple[float, float]:
    return 111.32 * float(np.cos(np.radians(lat))), 110.574


@lru_cache(maxsize=4)
def load_env(aoi_id: str) -> tuple[tuple[str, float, float], ...]:
    try:
        path: Path = safe_join(settings().env_dir, f"{aoi_id}.csv")
    except Exception:
        return ()
    if not path.is_file():
        return ()
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append(
                    (
                        r.get("date", ""),
                        float(r.get("rainfall_mm") or 0.0),
                        float(r.get("temp_max_c") or 0.0),
                    )
                )
    except Exception as exc:
        log.warning("env csv unreadable for %s: %s", aoi_id, exc)
        return ()
    return tuple(rows)


def rainfall_window(aoi_id: str, upto: date | None, days: int) -> float:
    rows = load_env(aoi_id)
    if not rows or upto is None:
        return 0.0
    start = upto - timedelta(days=days)
    total = 0.0
    for d, rain, _ in rows:
        try:
            when = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= when <= upto:
            total += rain
    return total


def mean_temp(aoi_id: str) -> float:
    rows = load_env(aoi_id)
    vals = [t for _, _, t in rows if t]
    return float(np.mean(vals)) if vals else 0.0


@lru_cache(maxsize=1)
def _load_model():
    try:
        path: Path = safe_join(settings().models_dir, MODEL_FILE)
    except Exception:
        return None
    if not path.is_file():
        return None
    try:
        import joblib

        bundle = joblib.load(path)
    except Exception as exc:
        log.warning("risk model failed to load: %s", exc)
        return None
    if list(bundle.get("features") or []) != CELL_FEATURES:
        log.warning("risk model feature order mismatch; ignoring the model")
        return None
    return bundle


def model_info() -> dict[str, str]:
    bundle = _load_model()
    if bundle is None:
        return {
            "risk_model": "weighted_heuristic_v1 (within-AOI ranking)",
            "risk_auc": "n/a - not a fitted model",
        }
    return {
        "risk_model": str(bundle.get("version", "gb")),
        "risk_auc": str(bundle.get("auc", "unreported")),
    }


def _normalise(name: str, value: float) -> float:
    scale = NORMALISERS.get(name, 1.0)
    if name == "dist_to_event_km":
        # closer is riskier
        return float(np.clip(1.0 - value / scale, 0.0, 1.0))
    if name in ("mean_d_ndvi",):
        # vegetation loss is a negative delta
        return float(np.clip(-value / scale, 0.0, 1.0))
    return float(np.clip(abs(value) / scale, 0.0, 1.0))


# The weighted sum's absolute value depends on how hazy or how changed a
# particular pair happens to be, so on one scene every cell lands in "high" and
# on another every cell lands in "low" - either way the heat layer reads as
# broken. Ranking within the AOI makes the score a *relative* propensity, which
# is what this is honestly measuring. Describe it that way: a within-AOI risk
# ranking calibrated per deployment, not an absolute probability.
CALIBRATION_EXPONENT = 1.8


def _calibrate(raw: list[float]) -> list[float]:
    arr = np.asarray(raw, dtype="float64")
    if arr.size == 0:
        return []
    if float(arr.max() - arr.min()) < 1e-9:
        return [0.0] * arr.size
    order = arr.argsort()
    ranks = np.empty(arr.size, dtype="float64")
    ranks[order] = np.arange(arr.size)
    pct = ranks / max(arr.size - 1, 1)
    return [float(v) for v in np.clip(pct ** CALIBRATION_EXPONENT, 0.0, 1.0)]


def _primary_risk(cell_geom, events: list[DetectedEvent]) -> EventType:
    if not events:
        return EventType.no_change
    centre = cell_geom.centroid
    best, best_d = events[0], float("inf")
    for e in events:
        lat, lon = e.centroid
        d = (centre.x - lon) ** 2 + (centre.y - lat) ** 2
        if d < best_d:
            best, best_d = e, d
    return best.event_type


def score_risk(
    bundle,
    events: list[DetectedEvent],
    deltas: dict[str, np.ndarray | None],
    before_idx: dict[str, np.ndarray | None],
    mask: np.ndarray,
    warnings: list[str] | None = None,
) -> list[RiskCell]:
    meta = bundle.meta
    aoi_id = meta.get("aoi_id", "")

    h, w = bundle.before.shape[-2:]
    left, bottom, right, top = array_bounds(h, w, bundle.transform)

    grids: dict[str, np.ndarray] = {}
    for k in INDEX_NAMES:
        d = deltas.get(k)
        grids[f"mean_d_{k}"] = block_mean(d) if d is not None else np.zeros((GRID, GRID), "float32")
        b = before_idx.get(k)
        grids[f"before_{k}"] = block_mean(b) if b is not None else np.zeros((GRID, GRID), "float32")
    grids["changed_fraction"] = block_mean(mask.astype("float32"))

    after_date = None
    raw = meta.get("after_date")
    if raw:
        try:
            after_date = datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            after_date = None

    rain7 = rainfall_window(aoi_id, after_date, 7)
    rain30 = rainfall_window(aoi_id, after_date, 30)
    tmax = mean_temp(aoi_id)
    if not load_env(aoi_id) and warnings is not None:
        warnings.append(f"no environmental csv for {aoi_id}; rainfall features are zero")

    event_shapes = [shapely.geometry.shape(e.geometry.model_dump()) for e in events]
    event_union = shapely.union_all(event_shapes) if event_shapes else None

    dlon = (right - left) / GRID
    dlat = (top - bottom) / GRID
    mid_lat = (top + bottom) / 2.0
    km_lon, km_lat = _km_per_deg(mid_lat)

    model_bundle = _load_model()
    model = model_bundle["model"] if model_bundle else None

    cells: list[RiskCell] = []
    rows_for_model: list[list[float]] = []
    staged: list[tuple[str, object, dict[str, float]]] = []

    for r in range(GRID):
        for c in range(GRID):
            cell_left = left + c * dlon
            cell_top = top - r * dlat
            geom = box(cell_left, cell_top - dlat, cell_left + dlon, cell_top)
            centre = Point(cell_left + dlon / 2, cell_top - dlat / 2)

            if event_union is None:
                dist_km = NORMALISERS["dist_to_event_km"]
            else:
                d_deg = centre.distance(event_union)
                dist_km = float(np.hypot(d_deg * km_lon, d_deg * km_lat)) if d_deg > 0 else 0.0

            feats = {
                "mean_d_ndwi": float(grids["mean_d_ndwi"][r, c]),
                "mean_d_ndvi": float(grids["mean_d_ndvi"][r, c]),
                "changed_fraction": float(grids["changed_fraction"][r, c]),
                "dist_to_event_km": dist_km,
                "before_ndwi": float(grids["before_ndwi"][r, c]),
                "before_ndvi": float(grids["before_ndvi"][r, c]),
                "before_ndbi": float(grids["before_ndbi"][r, c]),
                "rainfall_7d_mm": rain7,
                "rainfall_30d_mm": rain30,
                "temp_max_c": tmax,
            }
            staged.append((f"c_{r:04d}_{c:04d}", geom, feats))
            rows_for_model.append([feats[n] for n in CELL_FEATURES])

    if model is not None:
        try:
            scores = [float(p[1]) for p in model.predict_proba(rows_for_model)]
            importances = dict(
                zip(CELL_FEATURES, getattr(model, "feature_importances_", []), strict=False)
            )
        except Exception as exc:
            log.warning("risk model inference failed (%s); using the heuristic", exc)
            if warnings is not None:
                warnings.append(f"risk model inference failed ({type(exc).__name__}); used heuristic")
            model = None

    if model is None:
        importances = dict(HEURISTIC_WEIGHTS)
        raw_scores = []
        for _, _, feats in staged:
            s = sum(w * _normalise(name, feats[name]) for name, w in HEURISTIC_WEIGHTS.items())
            raw_scores.append(s / sum(HEURISTIC_WEIGHTS.values()))
        scores = _calibrate(raw_scores)

    for (cell_id, geom, feats), score in zip(staged, scores, strict=True):
        # weight each importance by this cell's normalised value so two red cells
        # can report different reasons - that is what makes the layer read as a
        # model rather than a colour ramp
        weighted = {
            name: imp * _normalise(name, feats.get(name, 0.0))
            for name, imp in importances.items()
            if imp
        }
        top = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)[:3]
        total = sum(v for _, v in top)
        drivers = [
            RiskDriver(
                name=DRIVER_NAMES.get(name, name),
                contribution=round(v / total, 3) if total > 0 else 0.0,
            )
            for name, v in top
        ]

        score = float(np.clip(score, 0.0, 1.0))
        cells.append(
            RiskCell(
                cell_id=cell_id,
                risk_score=round(score, 4),
                risk_level=risk_level_for(score),
                primary_risk=_primary_risk(geom, events),
                geometry=shapely.geometry.mapping(geom),
                drivers=drivers,
            )
        )

    return cells
