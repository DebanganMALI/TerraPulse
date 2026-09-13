"""Train the event classifier from data/models/dataset.csv.

    python -m app.pipeline.train.train_classifier

Writes data/models/event_classifier.joblib and prints the numbers you are
allowed to quote.

Read this before quoting anything: the labels come from rule_label() unless a
human corrected them in the CSV. Cross-validated accuracy on rule-derived labels
measures how well the model reproduces the rules, NOT how well it identifies
real events. The report prints how many rows were hand-corrected so you can say
which of the two you have.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "train-tool-not-a-real-secret")

import numpy as np  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import classification_report, f1_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # noqa: E402

from app.config import settings  # noqa: E402
from app.pipeline.features import FEATURES  # noqa: E402

def _models_dir() -> Path:
    return Path(settings().models_dir)
VERSION = "rf_v1"


def load(path: Path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    if not rows:
        raise SystemExit(f"{path} is empty - run build_dataset first")
    X = np.array([[float(r[f]) for f in FEATURES] for r in rows], dtype="float64")
    y = np.array([r["label"] for r in rows])
    corrected = sum(1 for r in rows if r.get("rule_label") and r["rule_label"] != r["label"])
    aois = sorted({r["aoi_id"] for r in rows})
    return X, y, corrected, aois


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m app.pipeline.train.train_classifier")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    dataset = Path(args.dataset) if args.dataset else _models_dir() / "dataset.csv"
    X, y, corrected, aois = load(dataset)
    counts = Counter(y)
    print(f"{len(y)} samples from {len(aois)} AOI(s): {', '.join(aois)}")
    print("classes:", dict(counts))
    print(f"hand-corrected labels: {corrected}")

    # a class with fewer members than folds cannot be stratified, and a model
    # trained on 2 examples of a class is not a model
    keep = {c for c, n in counts.items() if n >= args.folds}
    dropped = set(counts) - keep
    if dropped:
        print(f"dropping classes with < {args.folds} samples: {sorted(dropped)}")
        m = np.array([label in keep for label in y])
        X, y = X[m], y[m]

    if len(set(y)) < 2:
        raise SystemExit(
            "only one class survives - the dataset cannot train a classifier. "
            "Add another AOI with a different event type, or keep the rule-based fallback."
        )

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=12, class_weight="balanced", random_state=42
    )

    cv = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=42)
    pred = cross_val_predict(clf, X, y, cv=cv)
    accuracy = float((pred == y).mean())
    macro_f1 = float(f1_score(y, pred, average="macro"))

    print(f"\n{args.folds}-fold cross-validated")
    print(f"  accuracy  {accuracy:.3f}")
    print(f"  macro F1  {macro_f1:.3f}")
    print(classification_report(y, pred, zero_division=0))

    # a handful of corrections does not make the labels independent of the
    # rules; require a real share before dropping the caveat
    circular = corrected < max(0.10 * len(y), 3)
    if circular and accuracy > 0.97:
        print("\n" + "!" * 70)
        print("This score is circular. The labels came from rule_label() and the")
        print("features include the very quantities those rules threshold on, so the")
        print("model is reproducing a lookup table, not learning anything. Do NOT")
        print("quote this as accuracy. Hand-correct labels in the dataset CSV, or add")
        print("AOIs with other event types, or ship the rule-based fallback and say so.")
        print("!" * 70)

    clf.fit(X, y)
    importances = sorted(
        zip(FEATURES, clf.feature_importances_), key=lambda kv: kv[1], reverse=True
    )
    print("feature importances:")
    for name, imp in importances:
        print(f"  {name:<16} {imp:.3f}")

    out = Path(args.out) if args.out else _models_dir() / "event_classifier.joblib"
    out.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(
        {
            "model": clf,
            "features": FEATURES,
            "version": VERSION,
            # the caveat travels with the number so it cannot surface bare in
            # model_info, the API response, or a slide
            "accuracy": (
                f"{accuracy:.3f} vs rule labels (circular - not ground truth)"
                if circular
                else f"{accuracy:.3f} ({corrected} of {len(y)} labels photo-interpreted)"
            ),
            "macro_f1": f"{macro_f1:.3f}",
            "n_samples": len(y),
            "n_hand_corrected": corrected,
            "aois": aois,
            "label_source": "rule_label weak supervision" if corrected == 0
                            else f"rule_label with {corrected} hand corrections",
        },
        out,
    )
    print(f"\nwrote {out}")

    honest = (
        "Labels are rule-derived, so this measures how well the model reproduces "
        "the rules, not ground-truth accuracy."
        if corrected == 0
        else f"Labels are rule-derived with {corrected} hand corrections."
    )
    print("\nSay this, not just the number:")
    print(f"  {args.folds}-fold CV, n={len(y)}, accuracy {accuracy:.3f}, macro F1 {macro_f1:.3f}.")
    print(f"  {honest}")

    (out.parent / "classifier_report.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "n_samples": len(y),
                "n_hand_corrected": corrected,
                "aois": aois,
                "classes": {k: int(v) for k, v in Counter(y).items()},
                "cv_folds": args.folds,
                "accuracy": round(accuracy, 4),
                "macro_f1": round(macro_f1, 4),
                "feature_importances": {k: round(float(v), 4) for k, v in importances},
                "label_source": "rule_label weak supervision"
                if corrected == 0
                else f"rule_label + {corrected} hand corrections",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out.parent / 'classifier_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
