"""Tests for YouTube search functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from spotifytoyoutube.youtube_search import YouTubeSearcher, YouTubeResult


class TestYouTubeResult:
    """Tests for YouTubeResult dataclass."""

    def test_from_yt_dlp_info(self, sample_youtube_result: dict) -> None:
        """YouTubeResult can be created from yt-dlp info dict."""
        result = YouTubeResult.from_yt_dlp_info(sample_youtube_result)

        assert result.video_id == "dQw4w9WgXcQ"
        assert result.title == "Test Artist - Test Song"
        assert result.duration_seconds == 180
        assert result.audio_bitrate == 160

    def test_url_property(self) -> None:
        """url property returns full YouTube URL."""
        result = YouTubeResult(
            video_id="abc123",
            title="Test",
            duration_seconds=180,
            audio_bitrate=128,
            audio_codec="opus",
        )
        assert result.url == "https://www.youtube.com/watch?v=abc123"

    def test_from_yt_dlp_info_handles_missing_audio_info(self) -> None:
        """YouTubeResult handles missing audio bitrate gracefully."""
        info = {
            "id": "abc123",
            "title": "Test",
            "duration": 180,
        }
        result = YouTubeResult.from_yt_dlp_info(info)
        assert result.audio_bitrate == 0


class TestYouTubeSearcher:
    """Tests for YouTubeSearcher class."""

    @patch("spotifytoyoutube.youtube_search.yt_dlp.YoutubeDL")
    def test_search_returns_results(self, mock_ydl_class: Mock) -> None:
        """search returns list of YouTubeResult objects."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)

        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "video1",
                    "title": "Artist - Song",
                    "duration": 180,
                    "acodec": "opus",
                    "abr": 160,
                },
                {
                    "id": "video2",
                    "title": "Artist - Song (Official)",
                    "duration": 185,
                    "acodec": "opus",
                    "abr": 128,
                },
            ]
        }

        searcher = YouTubeSearcher()
        results = searcher.search("Artist - Song", max_results=5)

        assert len(results) == 2
        assert results[0].video_id == "video1"
        assert results[1].video_id == "video2"

    @patch("spotifytoyoutube.youtube_search.yt_dlp.YoutubeDL")
    def test_search_handles_no_results(self, mock_ydl_class: Mock) -> None:
        """search returns empty list when no results found."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        searcher = YouTubeSearcher()
        results = searcher.search("nonexistent query")

        assert results == []

    @patch("spotifytoyoutube.youtube_search.yt_dlp.YoutubeDL")
    def test_search_respects_max_results(self, mock_ydl_class: Mock) -> None:
        """search respects max_results parameter."""
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)

        searcher = YouTubeSearcher()
        searcher.search("query", max_results=3)

        # Verify the search URL contains the correct number
        call_args = mock_ydl.extract_info.call_args
        assert "ytsearch3:" in call_args[0][0]
