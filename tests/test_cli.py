"""Tests for CLI commands."""

import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from spotifytoyoutube.cli import main, auth, fetch, match


class TestAuthCommand:
    """Tests for auth command."""

    @patch.dict("os.environ", {
        "SPOTIFY_CLIENT_ID": "test_id",
        "SPOTIFY_CLIENT_SECRET": "test_secret",
    })
    @patch("spotifytoyoutube.cli.SpotifyAuthenticator")
    def test_auth_with_env_vars(self, mock_auth: Mock) -> None:
        """auth command uses environment variables for credentials."""
        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance
        mock_client = Mock()
        mock_auth_instance.get_client.return_value = mock_client
        mock_client.current_user.return_value = {"display_name": "Test User"}

        runner = CliRunner()
        result = runner.invoke(auth)

        assert result.exit_code == 0
        assert "Test User" in result.output

    @patch.dict("os.environ", {}, clear=True)
    def test_auth_without_credentials_fails(self) -> None:
        """auth command fails without credentials."""
        runner = CliRunner()
        result = runner.invoke(auth)

        assert result.exit_code != 0
        assert "SPOTIFY_CLIENT_ID" in result.output or "credentials" in result.output.lower()


class TestFetchCommand:
    """Tests for fetch command."""

    @patch.dict("os.environ", {
        "SPOTIFY_CLIENT_ID": "test_id",
        "SPOTIFY_CLIENT_SECRET": "test_secret",
    })
    @patch("spotifytoyoutube.cli.SpotifyAuthenticator")
    @patch("spotifytoyoutube.cli.SpotifyClient")
    def test_fetch_outputs_tracks(
        self, mock_client_class: Mock, mock_auth: Mock
    ) -> None:
        """fetch command outputs liked tracks."""
        from spotifytoyoutube.spotify_client import Track

        mock_auth_instance = Mock()
        mock_auth.return_value = mock_auth_instance

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_liked_songs.return_value = iter([
            Track(id="1", name="Song 1", artist="Artist 1", album="Album 1", duration_seconds=180),
            Track(id="2", name="Song 2", artist="Artist 2", album="Album 2", duration_seconds=200),
        ])

        runner = CliRunner()
        result = runner.invoke(fetch, ["--limit", "2"])

        assert result.exit_code == 0
        assert "Artist 1" in result.output


class TestMatchCommand:
    """Tests for match command."""

    @patch.dict("os.environ", {
        "SPOTIFY_CLIENT_ID": "test_id",
        "SPOTIFY_CLIENT_SECRET": "test_secret",
    })
    @patch("spotifytoyoutube.cli.SpotifyAuthenticator")
    @patch("spotifytoyoutube.cli.SpotifyClient")
    @patch("spotifytoyoutube.cli.YouTubeSearcher")
    @patch("spotifytoyoutube.cli.TrackMatcher")
    def test_match_outputs_youtube_urls(
        self,
        mock_matcher_class: Mock,
        mock_searcher_class: Mock,
        mock_client_class: Mock,
        mock_auth: Mock,
    ) -> None:
        """match command outputs YouTube URLs."""
        # Setup mocks
        mock_auth.return_value = Mock()

        mock_track = Mock()
        mock_track.name = "Song"
        mock_track.artist = "Artist"
        mock_track.search_query = "Artist - Song"

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_liked_songs.return_value = iter([mock_track])

        mock_yt_result = Mock()
        mock_yt_result.url = "https://www.youtube.com/watch?v=abc123"
        mock_yt_result.title = "Artist - Song"
        mock_yt_result.audio_bitrate = 320

        mock_match = Mock()
        mock_match.track = mock_track
        mock_match.youtube_result = mock_yt_result
        mock_match.title_similarity = 0.95
        mock_match.audio_bitrate = 320

        mock_matcher = Mock()
        mock_matcher_class.return_value = mock_matcher
        mock_matcher.find_best_match.return_value = mock_match

        runner = CliRunner()
        result = runner.invoke(match, ["--limit", "1"])

        assert result.exit_code == 0
        assert "youtube.com" in result.output
