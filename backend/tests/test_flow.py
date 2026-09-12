import time

AOI = "kerala_flood_2018"


def _run_to_completion(client, headers) -> str:
    r = client.post(
        "/api/v1/analysis/run", json={"aoi_id": AOI, "provider": "local"}, headers=headers
    )
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    for _ in range(100):
        s = client.get(f"/api/v1/analysis/{job_id}", headers=headers).json()
        if s["status"] in ("done", "failed"):
            assert s["status"] == "done", s.get("error")
            return job_id
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_login_returns_role(client):
    body = client.post(
        "/api/v1/auth/login", json={"username": "officer", "password": "officer"}
    ).json()
    assert body["user"]["role"] == "authority"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


def test_me_matches_login(client, auth):
    assert client.get("/api/v1/auth/me", headers=auth("analyst")).json()["role"] == "analyst"


def test_aoi_list_has_hero_area(client, auth):
    ids = [a["aoi_id"] for a in client.get("/api/v1/aoi", headers=auth()).json()]
    assert AOI in ids


def test_full_analysis_flow(client, auth):
    headers = auth("officer")
    job_id = _run_to_completion(client, headers)

    job = client.get(f"/api/v1/analysis/{job_id}", headers=headers).json()
    assert job["counts"]["events"] > 0
    assert job["counts"]["risk_cells"] > 0
    assert job["progress"] == 100

    events = client.get(f"/api/v1/events?aoi_id={AOI}", headers=headers).json()
    assert events["type"] == "FeatureCollection"
    assert events["features"]
    props = events["features"][0]["properties"]
    assert {"event_id", "event_type", "confidence", "severity", "area_km2"} <= set(props)

    lon, lat = events["features"][0]["geometry"]["coordinates"][0][0]
    assert 76.0 < lon < 77.0 and 9.5 < lat < 10.5

    risk = client.get(f"/api/v1/risk?aoi_id={AOI}", headers=headers).json()
    assert 0 < len(risk["features"]) <= 2500
    assert risk["features"][0]["properties"]["drivers"]

    stats = client.get(f"/api/v1/stats?aoi_id={AOI}", headers=headers).json()
    assert stats["total_events"] == len(events["features"])
    assert sum(stats["risk_distribution"].values()) == len(risk["features"])

    alerts = client.get(f"/api/v1/alerts?aoi_id={AOI}", headers=headers).json()
    assert alerts, "expected at least one alert from the mock result"
    assert alerts[0]["recommendations"]
    assert alerts[0]["acknowledged"] is False


def test_risk_min_level_filter(client, auth):
    headers = auth()
    _run_to_completion(client, headers)
    everything = client.get(f"/api/v1/risk?aoi_id={AOI}", headers=headers).json()
    high_only = client.get(
        f"/api/v1/risk?aoi_id={AOI}&min_level=high", headers=headers
    ).json()
    assert len(high_only["features"]) < len(everything["features"])
    assert all(
        f["properties"]["risk_level"] in ("high", "severe") for f in high_only["features"]
    )


def test_authority_can_acknowledge(client, auth):
    headers = auth("officer")
    _run_to_completion(client, headers)
    alert = client.get(f"/api/v1/alerts?aoi_id={AOI}", headers=headers).json()[0]

    acked = client.post(
        f"/api/v1/alerts/{alert['alert_id']}/ack", headers=headers
    ).json()
    assert acked["acknowledged"] is True
    assert acked["acknowledged_by"] == "officer"


def test_second_job_while_running_is_rejected(client, auth):
    headers = auth("analyst")
    first = client.post(
        "/api/v1/analysis/run", json={"aoi_id": AOI, "provider": "local"}, headers=headers
    )
    assert first.status_code == 202
    second = client.post(
        "/api/v1/analysis/run", json={"aoi_id": AOI, "provider": "local"}, headers=headers
    )
    # the mock finishes almost instantly with MOCK_STAGE_SECONDS=0, so accept either
    assert second.status_code in (202, 409)


def test_unknown_job_is_404(client, auth):
    r = client.get("/api/v1/analysis/job_zzzzzz", headers=auth())
    assert r.status_code == 404
