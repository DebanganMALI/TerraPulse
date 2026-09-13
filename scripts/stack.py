import re
import sys
from pathlib import Path

import rasterio

ORDER = ["B02", "B03", "B04", "B08", "B11"]   # blue, green, red, nir, swir

src_dir, out_path = Path(sys.argv[1]), sys.argv[2]

# Copernicus names exports like
# 2018-02-23-00_00_..._Sentinel-2_L2A_B02_(Raw).tiff, so match the band token
# rather than the whole filename. B8A must not match B08.
def find(band: str) -> Path:
    pat = re.compile(rf"(?<![0-9A-Za-z]){band}(?![0-9A-Za-z])")
    hits = [p for p in src_dir.iterdir() if p.suffix.lower() in (".tif", ".tiff") and pat.search(p.name)]
    if not hits:
        raise SystemExit(f"no file for {band} in {src_dir}")
    if len(hits) > 1:
        raise SystemExit(f"{band} is ambiguous: {[h.name for h in hits]}")
    return hits[0]

paths = [find(b) for b in ORDER]
for b, p in zip(ORDER, paths):
    print(f"  {b} <- {p.name}")

with rasterio.open(paths[0]) as ref:
    profile = ref.profile
    profile.update(count=len(ORDER), dtype="uint16", compress="deflate")
    shape = (ref.height, ref.width)

with rasterio.open(out_path, "w", **profile) as dst:
    for i, p in enumerate(paths, start=1):
        with rasterio.open(p) as src:
            if (src.height, src.width) != shape:
                raise SystemExit(f"{p.name} is {src.height}x{src.width}, expected {shape[0]}x{shape[1]}")
            dst.write(src.read(1).astype("uint16"), i)

print(f"{out_path} -> {len(ORDER)} bands, {shape[0]}x{shape[1]}")
