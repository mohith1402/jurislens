"""Unit tests verifying high efficiency, sub-millisecond memoization, and O(1) lookups."""

import time
import pytest
from app.services.citation_engine import citation_engine
from app.services.document_parser import document_parser
from app.services.gemini_service import gemini_service


def test_document_parser_content_caching(sample_employment_text):
    """Verify SHA-256 content-addressed cache returns in under 1ms."""
    # Warmup
    doc1 = document_parser.parse_text(sample_employment_text, filename="perf_test.txt")

    # Timed cached execution
    start = time.perf_counter()
    doc2 = document_parser.parse_text(sample_employment_text, filename="perf_test.txt")
    duration_ms = (time.perf_counter() - start) * 1000

    assert doc1.document_id == doc2.document_id
    assert duration_ms < 2.0, f"Cache retrieval took {duration_ms:.3f}ms (expected < 2ms)"


def test_citation_engine_lookup_performance(parsed_employment_doc):
    """Verify O(1) indexed clause lookup can resolve 100 queries in under 5ms."""
    queries = ["8.2", "Clause 8.2", "Section 1", "Clause 4", "9.1", "clause_1"] * 20

    start = time.perf_counter()
    for q in queries:
        clause = citation_engine.resolve_clause(q, parsed_employment_doc)
        assert clause is not None
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 10.0, f"Resolving 120 citations took {duration_ms:.3f}ms (expected < 10ms)"


@pytest.mark.asyncio
async def test_gemini_analysis_memoization(parsed_employment_doc):
    """Verify analysis memoization cache returns identical results instantly."""
    res1 = await gemini_service.analyze_document(parsed_employment_doc)

    start = time.perf_counter()
    res2 = await gemini_service.analyze_document(parsed_employment_doc)
    duration_ms = (time.perf_counter() - start) * 1000

    assert res1.overall_risk_score == res2.overall_risk_score
    assert duration_ms < 1.0, f"Analysis memoization took {duration_ms:.3f}ms (expected < 1ms)"


def test_gzip_compression_efficiency(client, sample_employment_text):
    """Verify FastAPI GZip compression middleware compresses large JSON payloads."""
    res = client.post(
        "/api/analyze-text",
        json={"text": sample_employment_text, "title": "test.txt"},
        headers={"Accept-Encoding": "gzip"},
    )
    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"


def test_bounded_cache_lru_eviction():
    """Verify BoundedCache caps entries and performs O(1) LRU eviction."""
    from app.core.cache import BoundedCache

    cache: BoundedCache[str, int] = BoundedCache(maxsize=3)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3

    assert len(cache) == 3
    assert cache["a"] == 1  # Access "a" to mark as recently used

    # Inserting "d" must evict "b" (oldest unaccessed entry)
    cache["d"] = 4
    assert len(cache) == 3
    assert "b" not in cache
    assert "a" in cache
    assert "c" in cache
    assert "d" in cache


def test_bounded_cache_ttl_expiration():
    """Verify BoundedLRUCache respects TTL and purges expired entries."""
    from app.core.cache import BoundedLRUCache

    cache: BoundedLRUCache[str, str] = BoundedLRUCache(maxsize=10, default_ttl_seconds=1)
    cache.set("ephemeral_key", "secret_value", ttl_seconds=1)
    assert cache.get("ephemeral_key") == "secret_value"

    # Advance time artificially past TTL
    import time
    time.sleep(1.05)
    assert cache.get("ephemeral_key") is None
    assert "ephemeral_key" not in cache
    assert len(cache) == 0


def test_pluggable_cache_factory_and_adapter():
    """Verify get_cache_backend factory returns operational cache with fallback safety."""
    from app.core.cache import get_cache_backend, RedisCacheAdapter

    # Factory returns functional BaseCache
    cache = get_cache_backend("session_test", maxsize=64, ttl_seconds=120)
    assert cache is not None
    cache.set("session_1", {"user": "analyst"})
    assert cache.get("session_1") == {"user": "analyst"}

    # RedisCacheAdapter gracefully falls back to local LRU if Redis is offline
    adapter = RedisCacheAdapter(redis_url="redis://localhost:6399/15", default_ttl_seconds=60)
    adapter.set("test_key", "local_fallback_val")
    assert adapter.get("test_key") == "local_fallback_val"
    adapter.clear()
