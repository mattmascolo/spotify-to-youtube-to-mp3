"""Spotify OAuth authentication handler."""

from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth


class SpotifyAuthenticator:
    """Handles Spotify OAuth authentication with token caching."""

    REQUIRED_SCOPES = ["user-library-read"]
    DEFAULT_REDIRECT_URI = "http://localhost:8888/callback"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cache_path: Path | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """
        Initialize Spotify authenticator.

        Args:
            client_id: Spotify application client ID
            client_secret: Spotify application client secret
            cache_path: Path to store OAuth token cache
            redirect_uri: OAuth redirect URI

        Raises:
            ValueError: If client_id or client_secret is empty
        """
        if not client_id:
            raise ValueError("client_id is required")
        if not client_secret:
            raise ValueError("client_secret is required")

        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_path = cache_path or Path.home() / ".spotifytoyoutube_cache" / ".spotify_token"
        self.redirect_uri = redirect_uri or self.DEFAULT_REDIRECT_URI
        self._client: spotipy.Spotify | None = None

    @property
    def scopes(self) -> list[str]:
        """Return required OAuth scopes."""
        return self.REQUIRED_SCOPES.copy()

    def get_client(self) -> spotipy.Spotify:
        """
        Get authenticated Spotify client.

        Returns:
            Authenticated spotipy.Spotify instance
        """
        if self._client is not None:
            return self._client

        # Ensure cache directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=" ".join(self.scopes),
            cache_path=str(self.cache_path),
        )

        self._client = spotipy.Spotify(auth_manager=auth_manager)
        return self._client
