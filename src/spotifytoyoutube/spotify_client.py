"""Spotify client for fetching user's liked songs."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import spotipy


@dataclass
class Track:
    """Represents a Spotify track with relevant metadata."""

    id: str
    name: str
    artist: str
    album: str
    duration_seconds: int

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Track":
        """
        Create Track from Spotify API response.

        Args:
            data: Track object from Spotify API

        Returns:
            Track instance
        """
        artists = data.get("artists", [])
        artist_name = artists[0]["name"] if artists else "Unknown Artist"

        return cls(
            id=data["id"],
            name=data["name"],
            artist=artist_name,
            album=data.get("album", {}).get("name", "Unknown Album"),
            duration_seconds=data.get("duration_ms", 0) // 1000,
        )

    @property
    def search_query(self) -> str:
        """Generate YouTube search query for this track."""
        return f"{self.artist} - {self.name}"


class SpotifyClient:
    """Client for interacting with Spotify API."""

    def __init__(self, sp: spotipy.Spotify) -> None:
        """
        Initialize Spotify client.

        Args:
            sp: Authenticated spotipy.Spotify instance
        """
        self._sp = sp

    def get_liked_songs(
        self,
        limit: int = 50,
        max_tracks: int | None = None,
    ) -> Iterator[Track]:
        """
        Fetch user's liked songs with pagination.

        Args:
            limit: Number of tracks per API request (max 50)
            max_tracks: Maximum total tracks to fetch (None for all)

        Yields:
            Track instances from the user's library
        """
        offset = 0
        fetched = 0

        while True:
            response = self._sp.current_user_saved_tracks(limit=limit, offset=offset)
            items = response.get("items", [])

            if not items:
                break

            for item in items:
                track_data = item.get("track")
                if track_data:
                    yield Track.from_api_response(track_data)
                    fetched += 1

                    if max_tracks and fetched >= max_tracks:
                        return

            if not response.get("next"):
                break

            offset += limit
