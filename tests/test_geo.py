import math

from app.geo import bearing_deg, distance_nm

INGOLSTADT = (48.7665, 11.4258)
MUENCHEN = (48.1372, 11.5756)


def test_distance_zero():
    assert distance_nm(*INGOLSTADT, *INGOLSTADT) == 0.0


def test_distance_ingolstadt_muenchen():
    # Luftlinie ca. 70 km = ca. 38 NM
    d = distance_nm(*INGOLSTADT, *MUENCHEN)
    assert 35 < d < 41


def test_bearing_north():
    assert math.isclose(bearing_deg(48.0, 11.0, 49.0, 11.0), 0.0, abs_tol=0.5)


def test_bearing_east():
    assert math.isclose(bearing_deg(48.0, 11.0, 48.0, 12.0), 90.0, abs_tol=0.5)


def test_bearing_muenchen_is_south():
    b = bearing_deg(*INGOLSTADT, *MUENCHEN)
    assert 170 < b < 195
