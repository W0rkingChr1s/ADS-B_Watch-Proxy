import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings

SAMPLE = [
    {
        "hex": "3c4b26",
        "flight": "DLH123",
        "lat": 48.80,
        "lon": 11.43,
        "alt_baro": 34000,
        "track": 180,
        "gs": 450,
        "baro_rate": 0,
    },
    {
        "hex": "3d1122",
        "flight": "DMEDX",
        "lat": 48.77,
        "lon": 11.44,
        "alt_baro": 1500,
        "track": 90,
        "gs": 120,
        "baro_rate": -800,
    },
]


class FakeClient:
    provider = type("P", (), {"name": "fake", "attribution": "test", "synthetic": False})()

    async def fetch_point(self, lat, lon, radius_nm):
        return SAMPLE

    async def aclose(self):
        return None


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(main, "client", FakeClient())
    settings.token = "testtoken"
    with TestClient(main.app) as c:
        monkeypatch.setattr(main, "client", FakeClient())
        yield c


def test_healthz(client):
    assert client.get("/healthz").status_code == 200


def test_requires_token(client):
    r = client.get("/v1/traffic?lat=48.7&lon=11.4")
    assert r.status_code == 401


def test_compact_default(client):
    r = client.get(
        "/v1/traffic?lat=48.7665&lon=11.4258&nm=50&alt_min=0&alt_max=45000",
        headers={"X-Api-Token": "testtoken"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0][0] in {"DLH123", "DMEDX"}


def test_altitude_band_applied(client):
    r = client.get(
        "/v1/traffic?lat=48.7665&lon=11.4258&nm=50&alt_min=0&alt_max=5000",
        headers={"X-Api-Token": "testtoken"},
    )
    assert [t[0] for t in r.json()] == ["DMEDX"]


def test_payload_stays_small(client):
    r = client.get(
        "/v1/traffic?lat=48.7665&lon=11.4258&nm=50&max=12",
        headers={"X-Api-Token": "testtoken"},
    )
    assert len(r.content) < 2048  # muss in den RAM der Uhr passen


def test_invalid_band(client):
    r = client.get(
        "/v1/traffic?lat=48.7&lon=11.4&alt_min=10000&alt_max=1000",
        headers={"X-Api-Token": "testtoken"},
    )
    assert r.status_code == 422
