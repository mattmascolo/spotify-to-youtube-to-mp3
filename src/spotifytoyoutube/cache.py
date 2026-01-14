"""Caching and rate limiting utilities."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class MatchCache:
    """Persistent cache for YouTube match results."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int = 86400 * 7,  # 1 week default
    ) -> None:
        """
        Initialize match cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.cache_dir = cache_dir or Path.home() / ".spotifytoyoutube_cache" / "matches"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Hash the key for safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get cached value for key.

        Args:
            key: Cache key (typically Spotify track ID)

        Returns:
            Cached data dict, or None if not found or expired
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        # Check TTL
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > self.ttl_seconds:
            cache_path.unlink(missing_ok=True)
            return None

        return data.get("value")

    def set(self, key: str, value: dict[str, Any]) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key (typically Spotify track ID)
            value: Data to cache
        """
        cache_path = self._get_cache_path(key)

        data = {
            "key": key,
            "value": value,
            "cached_at": time.time(),
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def clear(self) -> None:
        """Clear all cached entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(
        self,
        requests_per_second: float = 1.0,
        burst: int = 1,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Sustained request rate
            burst: Maximum burst size
        """
        self.requests_per_second = requests_per_second
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()

    def wait(self) -> None:
        """
        Wait until a request can be made.

        Blocks if rate limit would be exceeded.
        """
        now = time.time()

        # Add tokens based on time elapsed
        elapsed = now - self.last_update
        self.tokens = min(
            self.burst,
            self.tokens + elapsed * self.requests_per_second,
        )
        self.last_update = now

        if self.tokens >= 1:
            self.tokens -= 1
            return

        # Need to wait for token
        wait_time = (1 - self.tokens) / self.requests_per_second
        time.sleep(wait_time)
        self.tokens = 0
        self.last_update = time.time()
