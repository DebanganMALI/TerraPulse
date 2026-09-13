"""Build a labelled polygon dataset from the AOIs on disk.

    python -m app.pipeline.train.build_dataset                 # every AOI found
    python -m app.pipeline.train.build_dataset kerala_flood_2018
    python -m app.pipeline.train.build_dataset --min-area 0.10

Labels come from rule_label() - weak supervision, not ground truth. The CSV it
writes is meant to be opened and hand-corrected against the imagery before
training; the `label` column is what the trainer reads, and `rule_label` is kept
alongside so you can see which rows you changed.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "train-tool-not-a-real-secret")

from app.config import settings  # noqa: E402
from app.pipeline import detect, features, indices  # noqa: E402
from app.pipeline.align import align  # noqa: E402
from app.pipeline.providers import PROVIDERS  # noqa: E402
from app.pipeline.vectorize import centroid_lat_lon, to_polygons  # noqa: E402

def _default_out() -> Path:
    return Path(settings().models_dir) / "dataset.csv"

# lower than the pipeline's runtime filter on purpose: more, smaller regions
# make a usable training set out of a handful of scene pairs
TRAIN_MIN_AREA_KM2 = 0.10
MAX_REGIONS = 600


def rows_for(aoi_id: str, min_area: float) -> list[dict]:
    bundle = align(PROVIDERS["local"].load(aoi_id))
    before_idx = indices.compute(bundle.before, bundle.band_map)
    after_idx = indices.compute(bundle.after, bundle.band_map)

    valid, stats = detect.valid_mask(
        bundle.before, bundle.after, bundle.band_map, before_idx, after_idx
    )
    mask, deltas, offsets = detect.detect_change(before_idx, after_idx, valid=valid)
    regions = to_polygons(
        mask, bundle.transform, deltas, before_idx,
        min_area_km2=min_area, max_regions=MAX_REGIONS,
    )
    print(f"{aoi_id}: {len(regions)} regions  (usable {stats['valid']:.1%}, offsets {offsets})")

    out = []
    for i, region in enumerate(regions):
        f = features.row(region)
        lat, lon = centroid_lat_lon(region.geometry)
        label = features.rule_label(f)
        out.append({
            "aoi_id": aoi_id,
            "region_id": f"{aoi_id}_{i:04d}",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "label": label.value,
            "rule_label": label.value,
            **{k: round(v, 6) for k, v in f.items()},
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m app.pipeline.train.build_dataset")
    ap.add_argument("aoi_id", nargs="*", help="AOIs to include (default: all with rasters)")
    ap.add_argument("--min-area", type=float, default=TRAIN_MIN_AREA_KM2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    scenes = settings().scenes_dir
    targets = args.aoi_id or [
        d.name for d in sorted(scenes.iterdir())
        if d.is_dir() and (d / "before.tif").is_file() and (d / "after.tif").is_file()
    ]
    if not targets:
        print("no AOIs with before.tif and after.tif found", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for aoi in targets:
        try:
            rows.extend(rows_for(aoi, args.min_area))
        except Exception as exc:
            print(f"{aoi}: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)

    if not rows:
        print("no regions produced", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else _default_out()
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    print(f"\nwrote {len(rows)} rows to {out}")
    print("label distribution:", counts)
    print("\nNext: open the CSV, spot-check rows against the imagery, correct the")
    print("`label` column where the rule is clearly wrong, then run train_classifier.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
