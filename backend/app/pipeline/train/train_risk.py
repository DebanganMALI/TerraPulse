"""Train the risk model.

    python -m app.pipeline.train.train_risk

Labels: a grid cell is positive if it overlaps a detected event polygon.
Features are built from the BEFORE state only - before-indices, terrain proxies
and rainfall up to the before-date. Using after-scene features would leak the
answer and produce a meaningless 0.99 that a sharp judge will question in the
first thirty seconds.

Writes data/models/risk_model.joblib. Without it, risk.py falls back to the
documented weighted heuristic, which is a defensible thing to ship.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "train-tool-not-a-real-secret")

import numpy as np  # noqa: E402
import shapely  # noqa: E402
from shapely.geometry import box  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from app.config import settings  # noqa: E402
from app.pipeline import detect, indices  # noqa: E402
from app.pipeline.align import align  # noqa: E402
from app.pipeline.providers import PROVIDERS  # noqa: E402
from app.pipeline.risk import (  # noqa: E402
    CELL_FEATURES,
    GRID,
    block_mean,
    mean_temp,
    rainfall_window,
)
from app.pipeline.vectorize import to_polygons  # noqa: E402
from rasterio.transform import array_bounds  # noqa: E402

def _default_model() -> Path:
    return Path(settings().models_dir) / "risk_model.joblib"
VERSION = "gb_v1"

# max_depth 3 on purpose: shallow trees overfit less on a small sample and the
# importances stay interpretable
PARAMS = dict(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=42)


def samples_for(aoi_id: str):
    bundle = align(PROVIDERS["local"].load(aoi_id))
    before_idx = indices.compute(bundle.before, bundle.band_map)
    after_idx = indices.compute(bundle.after, bundle.band_map)

    valid, _ = detect.valid_mask(
        bundle.before, bundle.after, bundle.band_map, before_idx, after_idx
    )
    mask, deltas, _ = detect.detect_change(before_idx, after_idx, valid=valid)
    regions = to_polygons(mask, bundle.transform, deltas, before_idx, max_regions=600)
    if not regions:
        return np.empty((0, len(CELL_FEATURES))), np.empty(0)

    event_union = shapely.union_all([r.geometry for r in regions])

    h, w = bundle.before.shape[-2:]
    left, bottom, right, top = array_bounds(h, w, bundle.transform)
    dlon, dlat = (right - left) / GRID, (top - bottom) / GRID

    before_grids = {
        k: (block_mean(v) if v is not None else np.zeros((GRID, GRID), "float32"))
        for k, v in before_idx.items()
    }

    meta = bundle.meta
    from datetime import datetime

    try:
        before_date = datetime.strptime(str(meta.get("before_date"))[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        before_date = None

    # rainfall up to the BEFORE date, never the after date
    rain7 = rainfall_window(aoi_id, before_date, 7)
    rain30 = rainfall_window(aoi_id, before_date, 30)
    tmax = mean_temp(aoi_id)

    X, y = [], []
    for r in range(GRID):
        for c in range(GRID):
            cell = box(left + c * dlon, top - (r + 1) * dlat, left + (c + 1) * dlon, top - r * dlat)
            X.append([
                0.0,  # mean_d_ndwi   - after-derived, zeroed at training time
                0.0,  # mean_d_ndvi   - after-derived, zeroed at training time
                0.0,  # changed_fraction - after-derived, zeroed at training time
                0.0,  # dist_to_event_km - after-derived, zeroed at training time
                float(before_grids["ndwi"][r, c]),
                float(before_grids["ndvi"][r, c]),
                float(before_grids["ndbi"][r, c]),
                rain7,
                rain30,
                tmax,
            ])
            y.append(1 if cell.intersects(event_union) else 0)
    return np.asarray(X, dtype="float64"), np.asarray(y)


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m app.pipeline.train.train_risk")
    ap.add_argument("aoi_id", nargs="*")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scenes = settings().scenes_dir
    targets = args.aoi_id or [
        d.name for d in sorted(scenes.iterdir())
        if d.is_dir() and (d / "before.tif").is_file() and (d / "after.tif").is_file()
    ]

    Xs, ys = [], []
    for aoi in targets:
        try:
            X, y = samples_for(aoi)
            print(f"{aoi}: {len(y)} cells, {int(y.sum())} positive")
            if len(y):
                Xs.append(X)
                ys.append(y)
        except Exception as exc:
            print(f"{aoi}: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)

    if not Xs:
        raise SystemExit("no usable AOIs")

    X = np.vstack(Xs)
    y = np.concatenate(ys)
    print(f"\ntotal {len(y)} cells, {int(y.sum())} positive ({y.mean():.1%})")

    if y.sum() < 20 or (len(y) - y.sum()) < 20:
        raise SystemExit(
            "too few examples of one class to train honestly - keep the heuristic"
        )

    model = GradientBoostingClassifier(**PARAMS)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    auc = float(roc_auc_score(y, proba))
    print(f"5-fold cross-validated ROC AUC: {auc:.3f}")

    if len(targets) == 1:
        print("\nNote: a single AOI means the folds are spatially autocorrelated, so")
        print("this AUC is optimistic. Say that if you quote it.")

    model.fit(X, y)
    importances = sorted(
        zip(CELL_FEATURES, model.feature_importances_), key=lambda kv: kv[1], reverse=True
    )
    print("\nfeature importances:")
    for name, imp in importances:
        print(f"  {name:<20} {imp:.3f}")

    out = Path(args.out) if args.out else _default_model()
    out.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(
        {"model": model, "features": CELL_FEATURES, "version": VERSION,
         "auc": f"{auc:.3f}", "n_cells": int(len(y)), "aois": targets},
        out,
    )
    print(f"\nwrote {out}")

    (out.parent / "risk_report.json").write_text(
        json.dumps({"version": VERSION, "auc": round(auc, 4), "n_cells": int(len(y)),
                    "positive_rate": round(float(y.mean()), 4), "aois": targets,
                    "feature_importances": {k: round(float(v), 4) for k, v in importances},
                    "note": "features built from before-state only; single-AOI folds are "
                            "spatially autocorrelated"}, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
