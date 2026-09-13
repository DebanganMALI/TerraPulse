import logging
from functools import lru_cache

from app.config import settings
from app.pipeline import features
from app.pipeline.vectorize import Region
from app.schemas.common import EventType

log = logging.getLogger("terrapulse")

MODEL_PATH = "event_classifier.joblib"


def rule_label(f: dict[str, float]) -> tuple[EventType, float]:
    """Physically motivated rules. Used to bootstrap training labels, and as the
    runtime fallback when no trained model is present."""
    if f["d_ndwi"] > 0.15 and f["d_ndvi"] < -0.05:
        return EventType.flood, 0.72
    if f["d_ndwi"] < -0.15:
        return EventType.water_recession, 0.68
    if f["d_nbr"] < -0.25 and f["d_ndvi"] < -0.15:
        return EventType.wildfire_burn, 0.70
    if f["d_ndvi"] < -0.20 and abs(f["d_ndbi"]) < 0.05:
        return EventType.deforestation, 0.66
    if f["d_ndbi"] > 0.10 and f["d_ndvi"] < -0.10:
        return EventType.urban_expansion, 0.64
    return EventType.no_change, 0.50


@lru_cache(maxsize=1)
def _load():
    try:
        import joblib

        path = settings().models_dir / MODEL_PATH
        if not path.is_file():
            return None
        bundle = joblib.load(path)
        if list(bundle.get("features", [])) != features.FEATURES:
            log.warning("classifier feature order does not match; ignoring the model")
            return None
        return bundle
    except Exception as exc:
        log.warning("could not load classifier: %s", exc)
        return None


def classify(regions: list[Region]) -> tuple[list[tuple[EventType, float]], dict[str, str]]:
    if not regions:
        return [], {"classifier": "none"}

    bundle = _load()
    if bundle is None:
        out = [rule_label(features.vector(r)) for r in regions]
        return out, {"classifier": "rules", "accuracy": "n/a"}

    model = bundle["model"]
    X = features.matrix(regions)
    proba = model.predict_proba(X)
    labels = model.classes_
    out = []
    for row in proba:
        i = int(row.argmax())
        out.append((EventType(labels[i]), float(row[i])))
    info = {
        "classifier": str(bundle.get("version", "rf")),
        "accuracy": str(bundle.get("accuracy", "n/a")),
    }
    return out, info
