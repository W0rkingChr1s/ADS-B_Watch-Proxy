from app.filters import build_targets

HERE = (48.7665, 11.4258)


def ac(lat, lon, alt, flight="TEST123", rate=0):
    return {
        "hex": "3c4b26",
        "flight": flight,
        "lat": lat,
        "lon": lon,
        "alt_baro": alt,
        "track": 180,
        "gs": 420,
        "baro_rate": rate,
    }


def test_altitude_band_filters_out():
    raw = [ac(48.8, 11.4, 35000)]
    assert build_targets(raw, *HERE, 50, 0, 10000, 10) == []


def test_altitude_band_keeps():
    raw = [ac(48.8, 11.4, 5000)]
    out = build_targets(raw, *HERE, 50, 0, 10000, 10)
    assert len(out) == 1
    assert out[0].callsign == "TEST123"


def test_ground_string_becomes_zero():
    raw = [ac(48.767, 11.426, "ground")]
    out = build_targets(raw, *HERE, 50, -100, 1000, 10)
    assert out[0].altitude_ft == 0


def test_missing_position_is_dropped():
    raw = [{"hex": "abc", "alt_baro": 3000}]
    assert build_targets(raw, *HERE, 50, 0, 40000, 10) == []


def test_sorted_by_distance_and_capped():
    raw = [
        ac(49.5, 11.4, 3000, "FAR"),
        ac(48.80, 11.43, 3000, "NEAR"),
        ac(49.0, 11.4, 3000, "MID"),
    ]
    out = build_targets(raw, *HERE, 200, 0, 40000, 2)
    assert [t.callsign for t in out] == ["NEAR", "MID"]


def test_vertical_trend():
    out = build_targets([ac(48.8, 11.4, 3000, "CLIMB", rate=1200)], *HERE, 50, 0, 40000, 5)
    assert out[0].vertical == 1
    out = build_targets([ac(48.8, 11.4, 3000, "DESC", rate=-900)], *HERE, 50, 0, 40000, 5)
    assert out[0].vertical == -1
    out = build_targets([ac(48.8, 11.4, 3000, "LEVEL", rate=50)], *HERE, 50, 0, 40000, 5)
    assert out[0].vertical == 0


def test_compact_payload_shape():
    out = build_targets([ac(48.8, 11.4, 3000)], *HERE, 50, 0, 40000, 5)
    compact = out[0].to_compact()
    assert len(compact) == 6
    assert isinstance(compact[0], str)


# --- Hoehenquelle: alt_baro vs. alt_geom ---------------------------------


def test_alt_geom_springt_ein_wenn_alt_baro_null():
    """alt_baro als vorhandener Null-Wert darf den Fallback nicht blockieren."""
    raw = [ac(48.8, 11.4, None) | {"alt_geom": 7000}]
    out = build_targets(raw, *HERE, 50, 0, 40000, 10)
    assert len(out) == 1
    assert out[0].altitude_ft == 7000


def test_alt_geom_springt_ein_wenn_alt_baro_fehlt():
    raw = [ac(48.8, 11.4, 0)]
    del raw[0]["alt_baro"]
    raw[0]["alt_geom"] = 7000
    out = build_targets(raw, *HERE, 50, 0, 40000, 10)
    assert out[0].altitude_ft == 7000


def test_alt_baro_hat_vorrang_vor_alt_geom():
    raw = [ac(48.8, 11.4, 5000) | {"alt_geom": 7000}]
    assert build_targets(raw, *HERE, 50, 0, 40000, 10)[0].altitude_ft == 5000


def test_ground_gewinnt_auch_gegen_alt_geom():
    """Am Boden ist am Boden - die geometrische Hoehe ist dort Rauschen."""
    raw = [ac(48.767, 11.426, "ground") | {"alt_geom": 150}]
    assert build_targets(raw, *HERE, 50, -100, 1000, 10)[0].altitude_ft == 0


def test_unerwarteter_string_faellt_auf_alt_geom_zurueck():
    raw = [ac(48.8, 11.4, "quatsch") | {"alt_geom": 7000}]
    assert build_targets(raw, *HERE, 50, 0, 40000, 10)[0].altitude_ft == 7000


def test_ohne_jede_hoehe_wird_verworfen():
    raw = [ac(48.8, 11.4, None)]
    assert build_targets(raw, *HERE, 50, 0, 40000, 10) == []
