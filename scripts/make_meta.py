import json, sys, rasterio
from rasterio.warp import transform_bounds

aoi, name, region, before_date, after_date, expected = sys.argv[1:7]
d = f"data/scenes/{aoi}"

with rasterio.open(f"{d}/before.tif") as src:
    left, bottom, right, top = transform_bounds(src.crs, "EPSG:4326", *src.bounds)

meta = {
    "aoi_id": aoi,
    "name": name,
    "region": region,
    "bbox": [round(left, 4), round(bottom, 4), round(right, 4), round(top, 4)],
    "center": [round((bottom + top) / 2, 4), round((left + right) / 2, 4)],
    "before_date": before_date,
    "after_date": after_date,
    "provider": "local",
    "expected_event": expected,
    "band_map": {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5},
}

with open(f"{d}/meta.json", "w", encoding="utf-8") as fh:
    json.dump(meta, fh, indent=2, ensure_ascii=False)

print(json.dumps(meta, indent=2))
