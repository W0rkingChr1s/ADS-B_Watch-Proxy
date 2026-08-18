"""Datenmodelle des Proxys."""

from dataclasses import dataclass


@dataclass(slots=True)
class Target:
    """Ein aufbereitetes Flugzeug, relativ zur Nutzerposition."""

    callsign: str
    hex_id: str
    bearing: int  # Grad rechtweisend, 0-359
    distance_nm: float  # gerundet auf 1 Nachkommastelle
    altitude_ft: int  # barometrisch, 0 = am Boden
    track: int  # Kurs ueber Grund in Grad, -1 = vom Upstream nicht gemeldet
    vertical: int  # -1 sinkt, 0 stabil, 1 steigt
    ground_speed: int  # Knoten

    def to_compact(self) -> list:
        """Kompaktformat fuer die Uhr: Array statt Dictionary spart massiv RAM."""
        return [
            self.callsign,
            self.bearing,
            round(self.distance_nm, 1),
            self.altitude_ft,
            self.track,
            self.vertical,
        ]

    def to_full(self) -> dict:
        """Ausfuehrliches Format fuer Debugging und Nicht-Uhr-Clients."""
        return {
            "callsign": self.callsign,
            "hex": self.hex_id,
            "bearing": self.bearing,
            "distance_nm": round(self.distance_nm, 1),
            "altitude_ft": self.altitude_ft,
            "track": self.track,
            "vertical": self.vertical,
            "gs": self.ground_speed,
        }
