def test_health_is_public(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["pipeline_mode"] == "mock"


def test_security_headers_present(client):
    h = client.get("/api/v1/health").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in h
    assert h["X-Request-ID"]


def test_docs_exempt_from_csp(client):
    assert "Content-Security-Policy" not in client.get("/docs").headers


def test_unknown_route_uses_error_envelope(client):
    body = client.get("/api/v1/nope").json()
    assert set(body) == {"detail", "code", "request_id"}


def test_openapi_renders(client):
    assert client.get("/openapi.json").status_code == 200
