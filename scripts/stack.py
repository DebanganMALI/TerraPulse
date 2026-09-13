import sys, rasterio

ORDER = ["B02", "B03", "B04", "B08", "B11"]   # blue, green, red, nir, swir

src_dir, out_path = sys.argv[1], sys.argv[2]
paths = [f"{src_dir}/{b}.tiff" for b in ORDER]

with rasterio.open(paths[0]) as ref:
    profile = ref.profile
    profile.update(count=len(ORDER), dtype="uint16", compress="deflate")

with rasterio.open(out_path, "w", **profile) as dst:
    for i, p in enumerate(paths, start=1):
        with rasterio.open(p) as src:
            dst.write(src.read(1).astype("uint16"), i)

print(out_path, "->", len(ORDER), "bands")
