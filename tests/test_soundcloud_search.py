"""Tests for SoundCloud searcher."""

from unittest.mock import MagicMock, Mock, patch

from spotifytoyoutube.soundcloud_search import SoundCloudSearcher
from spotifytoyoutube.youtube_search import YouTubeResult


class TestSoundCloudSearcher:
    @patch("spotifytoyoutube.soundcloud_search.yt_dlp.YoutubeDL")
    def test_search_uses_scsearch_prefix(self, mock_ydl_class: Mock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        searcher = SoundCloudSearcher()
        searcher.search("Artist - Song", max_results=5)

        called_url = mock_ydl.extract_info.call_args[0][0]
        assert called_url.startswith("scsearch5:")

    @patch("spotifytoyoutube.soundcloud_search.yt_dlp.YoutubeDL")
    def test_search_returns_results_with_soundcloud_urls(
        self, mock_ydl_class: Mock
    ) -> None:
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = {
            "entries": [
                {
                    "id": "123456789",
                    "title": "Artist - Song",
                    "duration": 180,
                    "abr": 128,
                    "acodec": "mp3",
                    "webpage_url": "https://soundcloud.com/artist/song",
                },
            ],
        }

        searcher = SoundCloudSearcher()
        results = searcher.search("Artist - Song")

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, YouTubeResult)
        assert result.url == "https://soundcloud.com/artist/song"

    @patch("spotifytoyoutube.soundcloud_search.yt_dlp.YoutubeDL")
    def test_search_handles_empty_results(self, mock_ydl_class: Mock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.return_value = None

        searcher = SoundCloudSearcher()
        assert searcher.search("nothing") == []

    @patch("spotifytoyoutube.soundcloud_search.yt_dlp.YoutubeDL")
    def test_search_catches_extract_errors(self, mock_ydl_class: Mock) -> None:
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = Mock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = Mock(return_value=False)
        mock_ydl.extract_info.side_effect = RuntimeError("network error")

        searcher = SoundCloudSearcher()
        assert searcher.search("anything") == []

    def test_get_video_info_returns_none(self) -> None:
        """SoundCloud entries carry full info — no second-pass fetch needed."""
        assert SoundCloudSearcher().get_video_info("anything") is None
