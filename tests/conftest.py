"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def sample_spotify_track() -> dict:
    """Sample Spotify track data for testing."""
    return {
        "track": {
            "id": "abc123",
            "name": "Test Song",
            "artists": [{"name": "Test Artist"}],
            "album": {"name": "Test Album"},
            "duration_ms": 180000,
        }
    }


@pytest.fixture
def sample_youtube_result() -> dict:
    """Sample yt-dlp search result for testing."""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Test Artist - Test Song",
        "duration": 180,
        "acodec": "opus",
        "abr": 160,
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
