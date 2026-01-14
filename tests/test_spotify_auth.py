"""Tests for Spotify authentication."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from spotifytoyoutube.spotify_auth import SpotifyAuthenticator


class TestSpotifyAuthenticator:
    """Tests for SpotifyAuthenticator class."""

    def test_init_requires_client_credentials(self) -> None:
        """Authenticator requires client_id and client_secret."""
        with pytest.raises(ValueError, match="client_id"):
            SpotifyAuthenticator(client_id="", client_secret="secret")

        with pytest.raises(ValueError, match="client_secret"):
            SpotifyAuthenticator(client_id="id", client_secret="")

    def test_init_sets_default_cache_path(self, tmp_path: Path) -> None:
        """Authenticator uses default cache path in home directory."""
        auth = SpotifyAuthenticator(
            client_id="test_id",
            client_secret="test_secret",
            cache_path=tmp_path / ".spotify_cache",
        )
        assert auth.cache_path == tmp_path / ".spotify_cache"

    def test_get_scopes_includes_library_read(self) -> None:
        """Required scopes include user-library-read."""
        auth = SpotifyAuthenticator(client_id="id", client_secret="secret")
        assert "user-library-read" in auth.scopes

    @patch("spotifytoyoutube.spotify_auth.spotipy.Spotify")
    @patch("spotifytoyoutube.spotify_auth.SpotifyOAuth")
    def test_get_client_returns_authenticated_spotify(
        self, mock_oauth: Mock, mock_spotify: Mock
    ) -> None:
        """get_client returns authenticated Spotify instance."""
        mock_oauth_instance = Mock()
        mock_oauth.return_value = mock_oauth_instance
        mock_spotify_instance = Mock()
        mock_spotify.return_value = mock_spotify_instance

        auth = SpotifyAuthenticator(client_id="id", client_secret="secret")
        client = auth.get_client()

        assert client == mock_spotify_instance
        mock_oauth.assert_called_once()
        mock_spotify.assert_called_once_with(auth_manager=mock_oauth_instance)
