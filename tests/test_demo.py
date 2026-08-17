"""Der Demo-Provider traegt den ersten Test - er muss selbst geprueft sein."""

import pytest
from fastapi.testclient import TestClient

from app import demo, main
from app.config import settings
from app.filters import build_targets
from app.geo import distance_nm
from app.upstream import AdsbClient

BERLIN = (52.5200, 13.4050)
INGOLSTADT = (48.7665, 11.4258)


def test_generates_full_fleet():
    ac = demo.generate(*INGOLSTADT, 25, 0.0)
    assert len(ac) == demo.FLEET_SIZE


def test_is_deterministic_per_position():
    a = demo.generate(*INGOLSTADT, 25, 0.0)
    b = demo.generate(*INGOLSTADT, 25, 0.0)
    assert a == b


def test_different_positions_give_different_fleets():
    a = demo.generate(*INGOLSTADT, 25, 0.0)
    b = demo.generate(*BERLIN, 25, 0.0)
    assert [t["hex"] for t in a] != [t["hex"] for t in b]


def test_traffic_moves_over_time():
    a = demo.generate(*INGOLSTADT, 25, 0.0)
    b = demo.generate(*INGOLSTADT, 25, 600.0)
    moved = [x for x, y in zip(a, b, strict=True) if (x["lat"], x["lon"]) != (y["lat"], y["lon"])]
    assert len(moved) >= demo.FLEET_SIZE // 2


def test_ground_targets_stay_put():
    a = demo.generate(*INGOLSTADT, 25, 0.0)
    b = demo.generate(*INGOLSTADT, 25, 3600.0)
    for x, y in zip(a, b, strict=True):
        if x["alt_baro"] == "ground":
            assert (x["lat"], x["lon"]) == (y["lat"], y["lon"])


def test_covers_ground_low_and_cruise():
    """Ohne diese drei Faelle testet der Demo-Modus das Hoehenband nicht."""
    alts = [t["alt_baro"] for t in demo.generate(*INGOLSTADT, 25, 0.0)]
    assert "ground" in alts
    assert any(isinstance(a, int) and 0 < a < 10000 for a in alts)
    assert any(isinstance(a, int) and a >= 18000 for a in alts)


@pytest.mark.parametrize("radius", [5, 25, 100])
def test_most_traffic_lands_inside_the_radius(radius):
    """Ein Demo-Modus, der ueberwiegend ausserhalb des Kreises liegt, zeigt
    ein leeres Radarbild - und damit genau nichts."""
    ac = demo.generate(*INGOLSTADT, radius, 0.0)
    inside = [t for t in ac if distance_nm(*INGOLSTADT, t["lat"], t["lon"]) <= radius]
    assert len(inside) >= demo.FLEET_SIZE // 2


def test_passes_through_the_real_filter_chain():
    ac = demo.generate(*INGOLSTADT, 25, 0.0)
    targets = build_targets(ac, *INGOLSTADT, 25, 0, 45000, 10)
    assert targets
    assert all(0 <= t.bearing < 360 for t in targets)
    assert all(t.distance_nm <= 25 for t in targets)
    assert targets == sorted(targets, key=lambda t: t.distance_nm)


async def test_client_uses_demo_without_network():
    client = AdsbClient("demo")
    assert client.provider.synthetic
    ac = await client.fetch_point(*INGOLSTADT, 25)
    assert len(ac) == demo.FLEET_SIZE
    await client.aclose()


def test_unknown_provider_message_mentions_demo():
    with pytest.raises(ValueError, match="demo"):
        AdsbClient("gibtsnicht")


@pytest.fixture()
def demo_api(monkeypatch):
    monkeypatch.setattr(settings, "provider", "demo")
    settings.token = "testtoken"
    with TestClient(main.app) as c:
        yield c


def test_endpoint_end_to_end(demo_api):
    r = demo_api.get(
        "/v1/traffic?lat=48.7665&lon=11.4258&nm=25&max=10",
        headers={"X-Api-Token": "testtoken"},
    )
    assert r.status_code == 200
    body = r.json()
    assert 0 < len(body) <= 10
    assert all(len(row) == 6 for row in body)
    assert len(r.content) < 2048


def test_healthz_flags_demo_mode(demo_api):
    assert demo_api.get("/healthz").json()["demo"] is True
