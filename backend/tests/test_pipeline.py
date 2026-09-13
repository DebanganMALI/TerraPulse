import json
import os

import numpy as np
import pytest
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_bounds

from app.pipeline import detect, indices, run_analysis
from app.pipeline.features import FEATURES, rule_label
from app.pipeline.vectorize import centroid_lat_lon, to_polygons
from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.schemas.common import EventType, risk_level_for

BBOX = (76.2204, 9.4599, 76.4401, 9.6793)
SIZE = 400


def _scene(water_slice):
    a = np.zeros((5, SIZE, SIZE), dtype="float32")
    a[0] = 0.045
    a[1] = 0.070
    a[2] = 0.055
    a[3] = 0.320
    a[4] = 0.200
    if water_slice is not None:
        a[1][water_slice] = 0.11
        a[3][water_slice] = 0.03
        a[2][water_slice] = 0.04
        a[4][water_slice] = 0.02
    return a


@pytest.fixture
def synthetic_aoi(tmp_path, monkeypatch):
    aoi = "test_flood_aoi"
    data = tmp_path / "data"
    scenes = data / "scenes" / aoi
    scenes.mkdir(parents=True)
    (data / "models").mkdir()
    (data / "env").mkdir()

    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("JWT_SECRET", "test-only")
    from app.config import settings

    settings.cache_clear()

    before = (_scene(np.s_[190:210, 50:350]) * 65535).astype("uint16")
    after = (_scene(np.s_[140:260, 50:350]) * 65535).astype("uint16")

    profile = dict(
        driver="GTiff", height=SIZE, width=SIZE, count=5, dtype="uint16",
        crs=CRS.from_epsg(4326), transform=from_bounds(*BBOX, SIZE, SIZE),
    )
    for name, arr in (("before", before), ("after", after)):
        with rasterio.open(scenes / f"{name}.tif", "w", **profile) as dst:
            dst.write(arr)

    (scenes / "meta.json").write_text(json.dumps({
        "aoi_id": aoi,
        "name": "Test Flood",
        "region": "Test",
        "bbox": [round(v, 4) for v in BBOX],
        "center": [round((BBOX[1] + BBOX[3]) / 2, 4), round((BBOX[0] + BBOX[2]) / 2, 4)],
        "before_date": "2018-02-03",
        "after_date": "2018-08-22",
        "provider": "local",
        "expected_event": "flood",
        "band_map": {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5},
    }), encoding="utf-8")

    yield aoi
    settings.cache_clear()


def test_indices_stay_in_range():
    arr = _scene(np.s_[100:200, 100:200])
    out = indices.compute(arr, {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5})
    for name, grid in out.items():
        assert grid is not None, name
        assert grid.min() >= -1.0001 and grid.max() <= 1.0001, name


def test_indices_have_no_nan_at_zero_pixels():
    arr = np.zeros((5, 20, 20), dtype="float32")
    out = indices.compute(arr, {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5})
    for grid in out.values():
        assert not np.isnan(grid).any()


def test_known_water_patch_is_detected():
    band_map = {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5}
    before = indices.compute(_scene(None), band_map)
    after = indices.compute(_scene(np.s_[100:200, 100:200]), band_map)
    mask, deltas = detect.detect_change(before, after)
    assert mask[150, 150] == 1
    assert mask[10, 10] == 0
    assert deltas["ndwi"][150, 150] > detect.THRESHOLDS["ndwi"]


def test_polygons_use_lon_lat_and_centroid_uses_lat_lon():
    band_map = {"blue": 1, "green": 2, "red": 3, "nir": 4, "swir": 5}
    before = indices.compute(_scene(None), band_map)
    after = indices.compute(_scene(np.s_[100:300, 100:300]), band_map)
    mask, deltas = detect.detect_change(before, after)
    regions = to_polygons(mask, from_bounds(*BBOX, SIZE, SIZE), deltas, before)

    assert regions
    poly = regions[0].geometry
    min_lon, min_lat, max_lon, max_lat = poly.bounds
    assert BBOX[0] <= min_lon and max_lon <= BBOX[2]
    assert BBOX[1] <= min_lat and max_lat <= BBOX[3]

    lat, lon = centroid_lat_lon(poly)
    assert BBOX[1] <= lat <= BBOX[3]
    assert BBOX[0] <= lon <= BBOX[2]


def test_rule_label_recognises_a_flood():
    f = dict.fromkeys(FEATURES, 0.0)
    f["d_ndwi"] = 0.4
    f["d_ndvi"] = -0.2
    assert rule_label(f) is EventType.flood


def test_run_analysis_output_satisfies_the_contract(synthetic_aoi):
    seen = []
    result = run_analysis(
        AnalysisRequest(aoi_id=synthetic_aoi, job_id="job_abc123"),
        lambda pct, stage: seen.append(pct),
    )

    AnalysisResult.model_validate(result.model_dump())
    assert result.aoi_id == synthetic_aoi
    assert seen and seen[-1] == 100 and seen == sorted(seen)
    assert result.events
    assert any(e.event_type is EventType.flood for e in result.events)
    assert 0 < len(result.risk_cells) <= 2500
    assert all(c.risk_level is risk_level_for(c.risk_score) for c in result.risk_cells)
    assert all(c.drivers for c in result.risk_cells)


def test_missing_model_degrades_to_rules_instead_of_raising(synthetic_aoi):
    result = run_analysis(AnalysisRequest(aoi_id=synthetic_aoi, job_id="job_abc124"))
    assert result.model_info["classifier"] == "rule_v1"
    assert any("rule-based" in w for w in result.warnings)


def test_missing_scene_never_raises():
    result = run_analysis(AnalysisRequest(aoi_id="no_such_aoi_here", job_id="job_abc125"))
    AnalysisResult.model_validate(result.model_dump())
    assert result.events == []
    assert result.warnings


def test_progress_callback_failure_does_not_kill_the_run(synthetic_aoi):
    def explode(pct, stage):
        raise RuntimeError("ui died")

    result = run_analysis(AnalysisRequest(aoi_id=synthetic_aoi, job_id="job_abc126"), explode)
    assert result.events
