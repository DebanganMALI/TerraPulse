from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.schemas.analysis import DetectedEvent
from app.schemas.common import EventType
from app.security.paths import safe_join

from . import features
from .vectorize import Region, centroid_lat_lon, geometry_dict

log = logging.getLogger("terrapulse.pipeline")

MODEL_FILE = "event_classifier.joblib"
RULE_CONFIDENCE = 0.5


@lru_cache(maxsize=1)
def _load() -> dict | None:
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
        log.warning("event classifier failed to load: %s", exc)
        return None

    saved = list(bundle.get("features") or [])
    if saved != features.FEATURES:
        # a silent wrong-order bug produces confident nonsense; make it loud
        log.warning("classifier feature order does not match FEATURES; ignoring the model")
        return None
    return bundle


def model_info() -> dict[str, str]:
    bundle = _load()
    if bundle is None:
        return {"classifier": "rule_v1", "accuracy": "n/a (rule-based fallback)"}
    return {
        "classifier": str(bundle.get("version", "rf")),
        "accuracy": str(bundle.get("accuracy", "unreported")),
        "macro_f1": str(bundle.get("macro_f1", "unreported")),
    }


def classify(regions: list[Region], warnings: list[str] | None = None) -> list[DetectedEvent]:
    if not regions:
        return []

    bundle = _load()
    rows = [features.row(r) for r in regions]

    if bundle is None:
        if warnings is not None:
            warnings.append("event classifier unavailable; used rule-based labels")
        labels = [features.rule_label(r) for r in rows]
        confidences = [RULE_CONFIDENCE] * len(rows)
    else:
        model = bundle["model"]
        X = [[r[name] for name in features.FEATURES] for r in rows]
        try:
            proba = model.predict_proba(X)
            classes = list(model.classes_)
            labels, confidences = [], []
            for p in proba:
                i = max(range(len(p)), key=lambda k: p[k])
                labels.append(EventType(classes[i]))
                confidences.append(float(p[i]))
        except Exception as exc:
            log.warning("classifier inference failed (%s); falling back to rules", exc)
            if warnings is not None:
                warnings.append(f"classifier inference failed ({type(exc).__name__}); used rules")
            labels = [features.rule_label(r) for r in rows]
            confidences = [RULE_CONFIDENCE] * len(rows)

    events: list[DetectedEvent] = []
    for region, label, conf in zip(regions, labels, confidences, strict=True):
        if label == EventType.no_change:
            continue
        events.append(
            DetectedEvent(
                event_type=label,
                confidence=round(min(max(conf, 0.0), 1.0), 3),
                area_km2=region.area_km2,
                centroid=centroid_lat_lon(region.geometry),
                geometry=geometry_dict(region.geometry),
                deltas={k: (None if v is None else round(v, 4)) for k, v in region.deltas.items()},
            )
        )
    return events
