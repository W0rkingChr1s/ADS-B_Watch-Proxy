import asyncio
import time

import pytest

from app.upstream import PROVIDERS, AdsbClient, RateLimiter, TtlCache


def test_all_providers_use_v2_scheme():
    for key, provider in PROVIDERS.items():
        assert provider.base_url.endswith("/v2"), key
        assert provider.base_url.startswith("https://"), key


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        AdsbClient("gibtsnicht")


def test_cache_hit_and_expiry():
    cache = TtlCache(ttl=0.05)
    cache.set("k", [1, 2, 3])
    assert cache.get("k") == [1, 2, 3]
    time.sleep(0.08)
    assert cache.get("k") is None


def test_cache_miss_returns_none():
    assert TtlCache(ttl=5).get("nope") is None


def test_cache_key_rounds_position():
    # Zwei Positionen ~200 m auseinander muessen denselben Cache-Eintrag treffen
    a = AdsbClient._cache_key(48.7665, 11.4258, 25)
    b = AdsbClient._cache_key(48.7668, 11.4261, 25)
    assert a == b


def test_cache_key_separates_radius():
    assert AdsbClient._cache_key(48.76, 11.42, 25) != AdsbClient._cache_key(48.76, 11.42, 50)


async def test_rate_limiter_enforces_interval():
    limiter = RateLimiter(min_interval=0.1)
    start = time.monotonic()
    await asyncio.gather(*(limiter.acquire() for _ in range(3)))
    elapsed = time.monotonic() - start
    # Drei Requests, zwei Wartepausen -> mindestens 0,2 s
    assert elapsed >= 0.19
