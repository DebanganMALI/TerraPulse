from app.schemas.analysis import AnalysisRequest, AnalysisResult
from app.schemas.common import RiskLevel, risk_level_for
from app.services.pipeline import get_pipeline

REQ = AnalysisRequest(aoi_id="kerala_flood_2018", job_id="job_abc123")


def test_pipeline_output_satisfies_contract():
    result = get_pipeline()(REQ)
    assert isinstance(result, AnalysisResult)
    AnalysisResult.model_validate(result.model_dump())


def test_pipeline_reports_progress_monotonically():
    seen: list[int] = []
    get_pipeline()(REQ, lambda pct, stage: seen.append(pct))
    assert seen == sorted(seen)
    assert seen[-1] == 100


def test_events_are_geojson_lon_lat_order():
    result = get_pipeline()(REQ)
    assert result.events
    for e in result.events:
        lon, lat = e.geometry.coordinates[0][0]
        assert -180 <= lon <= 180 and -90 <= lat <= 90
        # centroid is (lat, lon) per the contract - opposite order to the geometry
        assert abs(e.centroid[0] - lat) < 1.0
        assert abs(e.centroid[1] - lon) < 1.0


def test_risk_cells_within_leaflet_budget():
    result = get_pipeline()(REQ)
    assert 0 < len(result.risk_cells) <= 2500


def test_risk_level_matches_score():
    for cell in get_pipeline()(REQ).risk_cells:
        assert cell.risk_level == risk_level_for(cell.risk_score)


def test_risk_thresholds():
    assert risk_level_for(0.0) is RiskLevel.low
    assert risk_level_for(0.30) is RiskLevel.moderate
    assert risk_level_for(0.60) is RiskLevel.high
    assert risk_level_for(0.90) is RiskLevel.severe


def test_mock_is_deterministic():
    a, b = get_pipeline()(REQ), get_pipeline()(REQ)
    assert a.model_dump() == b.model_dump()
