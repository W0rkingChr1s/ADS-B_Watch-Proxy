"""Rohdaten -> Target-Liste. Hier passiert das eigentliche Ausduennen."""

from .geo import bearing_deg, distance_nm
from .models import Target


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _altitude_ft(raw: dict) -> int | None:
    """alt_baro kann die Zeichenkette 'ground' sein, dann 0 ft."""
    alt = raw.get("alt_baro", raw.get("alt_geom"))
    if alt is None:
        return None
    if isinstance(alt, str):
        return 0 if alt.lower() == "ground" else None
    return _to_int(alt)


def _vertical_trend(raw: dict, threshold: int = 200) -> int:
    rate = raw.get("baro_rate", raw.get("geom_rate"))
    rate = _to_int(rate)
    if rate > threshold:
        return 1
    if rate < -threshold:
        return -1
    return 0


def _callsign(raw: dict) -> str:
    for field in ("flight", "r", "hex"):
        value = raw.get(field)
        if value and str(value).strip():
            return str(value).strip()[:8]
    return "?"


def build_targets(
    aircraft: list[dict],
    lat: float,
    lon: float,
    radius_nm: float,
    alt_min: int,
    alt_max: int,
    max_targets: int,
) -> list[Target]:
    """Filtert nach Radius und Hoehenband, sortiert nach Distanz, kappt bei max_targets."""
    targets: list[Target] = []

    for raw in aircraft:
        a_lat, a_lon = raw.get("lat"), raw.get("lon")
        if a_lat is None or a_lon is None:
            continue  # Ziel ohne Position ist fuer ein Radarbild wertlos

        altitude = _altitude_ft(raw)
        if altitude is None or not (alt_min <= altitude <= alt_max):
            continue

        dist = distance_nm(lat, lon, float(a_lat), float(a_lon))
        if dist > radius_nm:
            continue

        targets.append(
            Target(
                callsign=_callsign(raw),
                hex_id=str(raw.get("hex", "")).lower(),
                bearing=int(round(bearing_deg(lat, lon, float(a_lat), float(a_lon)))) % 360,
                distance_nm=dist,
                altitude_ft=altitude,
                track=_to_int(raw.get("track")) % 360,
                vertical=_vertical_trend(raw),
                ground_speed=_to_int(raw.get("gs")),
            )
        )

    targets.sort(key=lambda t: t.distance_nm)
    return targets[:max_targets]
