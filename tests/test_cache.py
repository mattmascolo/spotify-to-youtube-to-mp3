"""Tests for caching functionality."""

import time
from pathlib import Path

from spotifytoyoutube.cache import MatchCache, RateLimiter


class TestMatchCache:
    """Tests for MatchCache class."""

    def test_cache_stores_and_retrieves(self, tmp_path: Path) -> None:
        """Cache stores and retrieves match results."""
        cache = MatchCache(cache_dir=tmp_path)

        cache.set("track123", {"url": "https://youtube.com/watch?v=abc"})
        result = cache.get("track123")

        assert result == {"url": "https://youtube.com/watch?v=abc"}

    def test_cache_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Cache returns None for missing keys."""
        cache = MatchCache(cache_dir=tmp_path)
        assert cache.get("nonexistent") is None

    def test_cache_respects_ttl(self, tmp_path: Path) -> None:
        """Cache entries expire after TTL."""
        cache = MatchCache(cache_dir=tmp_path, ttl_seconds=1)

        cache.set("track123", {"url": "test"})
        assert cache.get("track123") is not None

        time.sleep(1.1)
        assert cache.get("track123") is None

    def test_cache_persists_to_disk(self, tmp_path: Path) -> None:
        """Cache persists entries to disk."""
        cache1 = MatchCache(cache_dir=tmp_path)
        cache1.set("track123", {"url": "test"})

        # Create new cache instance
        cache2 = MatchCache(cache_dir=tmp_path)
        assert cache2.get("track123") == {"url": "test"}

    def test_cache_clear(self, tmp_path: Path) -> None:
        """Cache can be cleared."""
        cache = MatchCache(cache_dir=tmp_path)
        cache.set("track1", {"url": "test1"})
        cache.set("track2", {"url": "test2"})

        cache.clear()

        assert cache.get("track1") is None
        assert cache.get("track2") is None


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_requests_within_limit(self) -> None:
        """RateLimiter allows requests within rate limit."""
        limiter = RateLimiter(requests_per_second=10)

        for _ in range(5):
            limiter.wait()  # Should not block significantly

    def test_delays_requests_exceeding_limit(self) -> None:
        """RateLimiter delays requests exceeding rate limit."""
        limiter = RateLimiter(requests_per_second=2)

        start = time.time()
        for _ in range(4):
            limiter.wait()
        elapsed = time.time() - start

        # 4 requests at 2/sec should take ~1.5 seconds
        assert elapsed >= 1.0

    def test_burst_allows_initial_burst(self) -> None:
        """RateLimiter with burst allows initial burst."""
        limiter = RateLimiter(requests_per_second=1, burst=5)

        start = time.time()
        for _ in range(5):
            limiter.wait()
        elapsed = time.time() - start

        # Burst should allow 5 immediate requests
        assert elapsed < 1.0
