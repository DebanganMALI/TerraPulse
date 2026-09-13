"""Eyeball check: run detection on one AOI and write a PNG of the mask.

    python scripts/preview_mask.py <aoi_id>

If the mask does not visibly trace the feature you expect, the bands or the
reflectance scaling are wrong. Fix that before building anything on top.
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
# app.config reads .env relative to cwd, and data_dir is "../data" relative to
# backend/ — so run from there regardless of where this was invoked
os.chdir(BACKEND)

from app.pipeline import detect, indices  # noqa: E402
from app.pipeline.align import align  # noqa: E402
from app.pipeline.providers import PROVIDERS  # noqa: E402
from app.pipeline.vectorize import centroid_lat_lon, to_polygons  # noqa: E402

aoi = sys.argv[1]

b = PROVIDERS["local"].load(aoi)
print(f"loaded  {b.before.shape}  {b.crs}  aligned={b.aligned}")
print(f"reflectance scale: {b.meta.get('reflectance_scale')}")
print(f"before reflectance min/max: {b.before.min():.4f} / {b.before.max():.4f}")

b = align(b)
print(f"aligned {b.before.shape}  {b.crs}")

bi = indices.compute(b.before, b.band_map)
ai = indices.compute(b.after, b.band_map)
print("index ranges (before):",
      {k: (None if v is None else (round(float(v.min()), 2), round(float(v.max()), 2))) for k, v in bi.items()})

cloud = detect.cloud_mask(b.after, b.band_map)
if cloud is not None:
    print(f"cloud-masked pixels: {cloud.mean():.1%}")

mask, deltas = detect.detect_change(bi, ai, exclude=cloud)
print("delta ranges:", {k: (round(lo, 3), round(hi, 3)) for k, (lo, hi) in detect.delta_range(deltas).items()})
print(f"changed pixels: {int(mask.sum())} ({mask.mean():.1%} of scene)")

regions = to_polygons(mask, b.transform, deltas, bi)
print(f"regions: {len(regions)}")
for r in regions[:10]:
    lat, lon = centroid_lat_lon(r.geometry)
    print(f"  {r.area_km2:>8.2f} km2  ({lat:.4f}, {lon:.4f})  "
          f"dNDWI {r.deltas['ndwi']:+.3f}  dNDVI {r.deltas['ndvi']:+.3f}")


def rgb(arr, band_map):
    stack = np.stack([arr[band_map[c] - 1] for c in ("red", "green", "blue")], axis=-1)
    lo, hi = np.percentile(stack, (2, 98))
    return np.clip((stack - lo) / (hi - lo + 1e-9), 0, 1)


fig, ax = plt.subplots(1, 3, figsize=(16, 6))
ax[0].imshow(rgb(b.before, b.band_map)); ax[0].set_title(f"before  {b.meta.get('before_date', '')}")
ax[1].imshow(rgb(b.after, b.band_map)); ax[1].set_title(f"after  {b.meta.get('after_date', '')}")
ax[2].imshow(mask, cmap="magma"); ax[2].set_title(f"change mask - {len(regions)} regions")
for a in ax:
    a.axis("off")

out = ROOT / f"preview_{aoi}.png"
fig.tight_layout()
fig.savefig(out, dpi=110)
print("wrote", out)
