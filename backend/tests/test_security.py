import time

from jose import jwt

from app.config import settings

RUN = "/api/v1/analysis/run"
BODY = {"aoi_id": "kerala_flood_2018", "provider": "local"}


def test_health_is_public(client):
    assert client.get("/api/v1/health").status_code == 200


def test_protected_route_rejects_missing_token(client):
    r = client.get("/api/v1/aoi")
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_CREDENTIALS"


def test_protected_route_rejects_tampered_token(client, auth):
    good = auth("officer")["Authorization"].split()[1]
    bad = good[:-3] + ("aaa" if not good.endswith("aaa") else "bbb")
    r = client.get("/api/v1/aoi", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_token_signed_with_another_key_rejected(client):
    forged = jwt.encode(
        {"sub": "officer", "role": "authority", "exp": time.time() + 600},
        "not-the-real-secret",
        algorithm="HS256",
    )
    r = client.get("/api/v1/aoi", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_expired_token_rejected(client):
    s = settings()
    expired = jwt.encode(
        {"sub": "officer", "role": "authority", "exp": time.time() - 10},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    r = client.get("/api/v1/aoi", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
    assert r.json()["code"] == "TOKEN_EXPIRED"


def test_wrong_password_rejected(client):
    r = client.post(
        "/api/v1/auth/login", json={"username": "officer", "password": "wrong"}
    )
    assert r.status_code == 401


def test_unknown_user_and_wrong_password_are_indistinguishable(client):
    a = client.post("/api/v1/auth/login", json={"username": "officer", "password": "x"})
    b = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "x"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_viewer_cannot_trigger_analysis(client, auth):
    r = client.post(RUN, json=BODY, headers=auth("viewer"))
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN_ROLE"


def test_analyst_can_trigger_analysis(client, auth):
    r = client.post(RUN, json=BODY, headers=auth("analyst"))
    assert r.status_code == 202


def test_analyst_cannot_acknowledge_alerts(client, auth):
    r = client.post("/api/v1/alerts/al_x/ack", headers=auth("analyst"))
    assert r.status_code == 403


def test_path_traversal_rejected(client, auth):
    r = client.get("/api/v1/aoi/..%2F..%2Fetc", headers=auth())
    assert r.status_code in (400, 404, 422)


def test_unknown_aoi_is_404(client, auth):
    r = client.get("/api/v1/aoi/no_such_area", headers=auth())
    assert r.status_code == 404
    assert r.json()["code"] == "AOI_NOT_FOUND"


def test_extra_fields_are_rejected(client, auth):
    r = client.post(
        RUN, json={**BODY, "sneaky": "value"}, headers=auth("analyst")
    )
    assert r.status_code == 422


def test_error_envelope_shape(client):
    body = client.get("/api/v1/aoi").json()
    assert set(body) == {"detail", "code", "request_id"}
    assert body["request_id"]
