import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="terrapulse-test-")

os.environ.setdefault("JWT_SECRET", "test-secret-not-used-in-production")
os.environ.setdefault("PIPELINE_MODE", "mock")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("MOCK_STAGE_SECONDS", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

SEEDED = {"viewer": "viewer", "analyst": "analyst", "officer": "officer"}


@pytest.fixture(scope="session")
def client():
    with TestClient(create_app()) as c:
        yield c


def _token(client, username: str) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEEDED[username]},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth(client):
    def _headers(username: str = "officer") -> dict:
        return {"Authorization": f"Bearer {_token(client, username)}"}

    return _headers
