"""Synthetischer Verkehr fuer den ersten Test.

Zweck: die Watch App gegen ein laufendes Backend testen zu koennen, ohne dass
dafuer schon deployt sein muss und ohne einen Upstream anzufassen. Der Endpoint,
das Kompaktformat und der komplette Filterpfad sind dieselben wie im Echtbetrieb
- nur die Rohdaten kommen aus dieser Datei statt aus dem Netz.

Die Daten sind **deterministisch aus der Position abgeleitet**: derselbe Ort
liefert dieselbe Flotte. Bewegt wird ueber die Uhrzeit, damit sich das Radarbild
zwischen zwei Refreshes sichtbar aendert.
"""

import hashlib
import math

# Anzahl erzeugter Rohziele. Bewusst deutlich groesser als ADSB_MAX_TARGETS,
# damit Radiusfilter, Hoehenband und Top-N im Test tatsaechlich etwas zu tun haben.
FLEET_SIZE = 18

_AIRLINES = ("DLH", "EWG", "BER", "AUA", "SWR", "KLM", "AFR", "BAW", "RYR", "WZZ")


def _rand_stream(seed: str) -> list[float]:
    """Zwoelf reproduzierbare Werte in [0, 1) aus einem Seed.

    Kein `random`-Modul: das haette globalen Zustand und wuerde bei parallelen
    Requests unterschiedliche Ergebnisse liefern.
    """
    digest = hashlib.sha256(seed.encode()).digest()
    return [digest[i] / 256.0 for i in range(12)]


def _hex_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:6]


def _aircraft(index: int, lat: float, lon: float, radius_nm: float, elapsed_h: float) -> dict:
    """Ein Flugzeug auf gerader Bahn durch den Radiuskreis."""
    seed = f"{round(lat, 2)}:{round(lon, 2)}:{index}"
    r = _rand_stream(seed)

    # Kurs ueber Grund und Querabstand der Bahn zum Zentrum.
    track = r[0] * 360.0
    offset_nm = (r[1] * 1.8 - 0.9) * radius_nm

    # Laenge der Sehne durch den Kreis, plus etwas Vorlauf ausserhalb.
    half_chord = math.sqrt(max(radius_nm**2 - offset_nm**2, 0.0))
    leg_nm = 2.0 * half_chord + 0.2 * radius_nm
    if leg_nm <= 0.0:
        leg_nm = radius_nm

    # Hoehenprofil: Reiseflug ist der Normalfall, dazu etwas tiefer Verkehr und
    # ein Bodenziel - genau die Faelle, an denen sich das Hoehenband beweist.
    bucket = index % 6
    if bucket == 0:
        altitude: int | str = "ground"
        ground_speed = int(5 + r[2] * 15)
        rate = 0
    elif bucket == 1:
        altitude = int(800 + r[2] * 4200)
        ground_speed = int(90 + r[3] * 90)
        rate = int((r[4] * 2.0 - 1.0) * 1200)
    else:
        altitude = int(18000 + r[2] * 23000)
        ground_speed = int(380 + r[3] * 140)
        rate = int((r[4] * 2.0 - 1.0) * 500)

    # Fortschritt entlang der Bahn, zyklisch. Ein am Boden stehendes Ziel bewegt
    # sich nicht - sonst rutscht es ueber das halbe Vorfeld.
    if altitude == "ground":
        along_nm = (r[5] * 2.0 - 1.0) * min(radius_nm, 3.0)
    else:
        start = r[5] * leg_nm
        along_nm = ((start + ground_speed * elapsed_h) % leg_nm) - leg_nm / 2.0

    # Bahnkoordinaten -> Ost/Nord in NM.
    theta = math.radians(track)
    east_nm = along_nm * math.sin(theta) + offset_nm * math.cos(theta)
    north_nm = along_nm * math.cos(theta) - offset_nm * math.sin(theta)

    a_lat = lat + north_nm / 60.0
    cos_lat = math.cos(math.radians(lat))
    a_lon = lon + east_nm / (60.0 * (cos_lat if abs(cos_lat) > 1e-6 else 1e-6))

    callsign = f"{_AIRLINES[index % len(_AIRLINES)]}{int(r[6] * 900) + 100}"

    return {
        "hex": _hex_id(seed),
        "flight": callsign,
        "lat": round(a_lat, 5),
        "lon": round(a_lon, 5),
        "alt_baro": altitude,
        "track": round(track, 1),
        "gs": ground_speed,
        "baro_rate": rate,
    }


def generate(lat: float, lon: float, radius_nm: int, elapsed_s: float) -> list[dict]:
    """Rohdaten im ADSBx-v2-Schema, wie sie ein echter Upstream liefern wuerde."""
    elapsed_h = elapsed_s / 3600.0
    span = float(max(radius_nm, 1))
    return [_aircraft(i, lat, lon, span, elapsed_h) for i in range(FLEET_SIZE)]
