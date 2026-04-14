"""Shared pytest fixtures."""

import pytest

from spotifytoyoutube.matcher import MatchResult
from spotifytoyoutube.spotify_client import Track
from spotifytoyoutube.youtube_search import YouTubeResult


@pytest.fixture
def sample_spotify_track() -> dict:
    """Sample Spotify track data for testing."""
    return {
        "track": {
            "id": "abc123",
            "name": "Test Song",
            "artists": [
                {"name": "Test Artist", "id": "artist1"},
                {"name": "Featured Artist", "id": "artist2"},
            ],
            "album": {
                "name": "Test Album",
                "artists": [{"name": "Test Album Artist", "id": "artist1"}],
                "images": [{"url": "https://i.scdn.co/image/abc123", "width": 640}],
                "release_date": "2023-06-15",
            },
            "duration_ms": 180000,
            "popularity": 75,
            "explicit": False,
            "track_number": 3,
            "disc_number": 2,
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


@pytest.fixture
def sample_match_result() -> MatchResult:
    """Sample MatchResult for tagger tests."""
    track = Track(
        id="abc123",
        name="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration_seconds=180,
        all_artists=["Test Artist", "Featured Artist"],
        artist_id="artist1",
        album_artist="Test Album Artist",
        genres=["indie pop", "alternative"],
        release_date="2023-06-15",
        release_year=2023,
        popularity=75,
        explicit=False,
        track_number=3,
        disc_number=2,
        album_art_url="https://i.scdn.co/image/abc123",
    )
    yt_result = YouTubeResult(
        video_id="dQw4w9WgXcQ",
        title="Test Artist - Test Song",
        duration_seconds=180,
        audio_bitrate=160,
        audio_codec="opus",
    )
    return MatchResult(
        track=track,
        youtube_result=yt_result,
        title_similarity=0.95,
        duration_match=True,
        audio_bitrate=160,
    )
