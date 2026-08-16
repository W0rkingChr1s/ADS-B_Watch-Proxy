"""Upstream-Anbindung an die ADS-B-Aggregatoren.

Alle unterstuetzten Quellen sprechen das ADSBx-v2-Schema:
    GET /v2/point/{lat}/{lon}/{radius_nm}  ->  {"ac": [ ... ]}
Damit ist ein Providerwechsel eine reine Konfigurationsfrage.
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from .config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    auth_header: str | None = None
    attribution: str = ""


PROVIDERS: dict[str, Provider] = {
    "adsblol": Provider(
        name="adsb.lol",
        base_url="https://api.adsb.lol/v2",
        attribution="Data (c) adsb.lol contributors, ODbL 1.0",
    ),
    "airplaneslive": Provider(
        name="airplanes.live",
        base_url="https://api.airplanes.live/v2",
        attribution="Data from airplanes.live (non-commercial use)",
    ),
    "adsbone": Provider(
        name="adsb.one",
        base_url="https://api.adsb.one/v2",
        attribution="Data from adsb.one",
    ),
    "adsbexchange": Provider(
        name="ADS-B Exchange",
        base_url="https://adsbexchange-com1.p.rapidapi.com/v2",
        auth_header="X-RapidAPI-Key",
        attribution="Data from ADS-B Exchange (paid RapidAPI plan)",
    ),
}


class UpstreamError(RuntimeError):
    """Upstream nicht erreichbar oder liefert Murks."""


class RateLimiter:
    """Serialisiert Upstream-Requests und haelt den Mindestabstand ein.

    Die freien Aggregatoren limitieren auf 1 Request/Sekunde. Ohne das hier
    fliegen wir bei zwei parallelen Uhren-Requests sofort in ein 429.
    """

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class TtlCache:
    """Winziger In-Memory-Cache. Kein Redis noetig fuer eine Handvoll Clients."""

    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        entry = self._data.get(key)
        if entry is None:
            return None
        stamp, value = entry
        if time.monotonic() - stamp > self._ttl:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._data[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._data.clear()


class AdsbClient:
    """Holt Rohdaten vom konfigurierten Aggregator, mit Cache und Rate Limit."""

    def __init__(self, provider_key: str | None = None) -> None:
        key = (provider_key or settings.provider).lower()
        if key not in PROVIDERS:
            raise ValueError(f"Unbekannter Provider '{key}'. Erlaubt: {sorted(PROVIDERS)}")
        self.provider = PROVIDERS[key]
        self._cache = TtlCache(settings.cache_ttl)
        self._limiter = RateLimiter(settings.min_upstream_interval)
        self._client = httpx.AsyncClient(
            timeout=settings.upstream_timeout,
            headers={"User-Agent": "adsb-watch-garmin/0.1 (+github.com/W0rkingChr1s/ADS-B-Watch---Garmin)"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _cache_key(lat: float, lon: float, radius_nm: int) -> str:
        """Positionen auf ~1.1 km runden. Zwei Abfragen vom selben Standort
        treffen so denselben Cache-Eintrag."""
        return f"{round(lat, 2)}:{round(lon, 2)}:{radius_nm}"

    async def fetch_point(self, lat: float, lon: float, radius_nm: int) -> list[dict]:
        key = self._cache_key(lat, lon, radius_nm)
        cached = self._cache.get(key)
        if cached is not None:
            log.debug("Cache-Treffer fuer %s", key)
            return cached  # type: ignore[return-value]

        url = f"{self.provider.base_url}/point/{lat}/{lon}/{radius_nm}"
        headers = {}
        if self.provider.auth_header:
            if not settings.api_key:
                raise UpstreamError(f"{self.provider.name} braucht ADSB_API_KEY")
            headers[self.provider.auth_header] = settings.api_key

        await self._limiter.acquire()
        try:
            resp = await self._client.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            raise UpstreamError(f"{self.provider.name}: {exc}") from exc
        except ValueError as exc:
            raise UpstreamError(f"{self.provider.name}: ungueltiges JSON") from exc

        aircraft = payload.get("ac") or payload.get("aircraft") or []
        if not isinstance(aircraft, list):
            raise UpstreamError(f"{self.provider.name}: unerwartete Antwortstruktur")

        self._cache.set(key, aircraft)
        log.info("Upstream %s: %d Ziele fuer %s", self.provider.name, len(aircraft), key)
        return aircraft
