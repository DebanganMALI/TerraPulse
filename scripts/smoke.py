import sys, rasterio, numpy as np

aoi = sys.argv[1]
for name in ("before", "after"):
    with rasterio.open(f"data/scenes/{aoi}/{name}.tif") as src:
        a = src.read().astype("float32")
        print(f"{name}: {src.count} bands  {src.shape}  {src.crs}")
        print(f"  bounds {src.bounds}")
        print(f"  min {a.min():.1f}  max {a.max():.1f}  zeros {(a == 0).mean():.1%}")
