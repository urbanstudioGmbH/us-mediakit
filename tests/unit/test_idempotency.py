from us_mediakit.billing.idempotency import ResponseCache


def test_response_cache_roundtrip():
    cache = ResponseCache(ttl_seconds=60)
    cache.set("req-1", {"data": b"hello"})
    assert cache.get("req-1") == {"data": b"hello"}


def test_response_cache_miss():
    cache = ResponseCache(ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_response_cache_expires():
    cache = ResponseCache(ttl_seconds=-1)  # sofort abgelaufen
    cache.set("req-1", "value")
    assert cache.get("req-1") is None


def test_response_cache_evicts_when_full():
    cache = ResponseCache(ttl_seconds=60, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert len(cache._entries) == 2
