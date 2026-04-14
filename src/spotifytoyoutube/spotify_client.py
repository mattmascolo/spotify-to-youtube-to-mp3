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

    # Extended metadata (populated from API response)
    all_artists: list[str] | None = None
    artist_id: str | None = None
    genres: list[str] | None = None
    release_date: str | None = None
    release_year: int | None = None
    popularity: int | None = None
    explicit: bool | None = None
    track_number: int | None = None
    album_art_url: str | None = None

    # Audio features (populated via enrich_tracks)
    tempo: float | None = None
    energy: float | None = None
    danceability: float | None = None
    valence: float | None = None
    acousticness: float | None = None
    instrumentalness: float | None = None
    loudness: float | None = None
    speechiness: float | None = None
    liveness: float | None = None
    key: int | None = None
    time_signature: int | None = None
    mode: int | None = None

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
        artist_id = artists[0].get("id") if artists else None
        all_artists = [a["name"] for a in artists] if artists else None

        album = data.get("album", {})
        images = album.get("images", [])
        album_art_url = images[0]["url"] if images else None

        release_date = album.get("release_date")
        release_year = None
        if release_date:
            try:
                release_year = int(release_date[:4])
            except (ValueError, IndexError):
                pass

        return cls(
            id=data["id"],
            name=data["name"],
            artist=artist_name,
            album=album.get("name", "Unknown Album"),
            duration_seconds=data.get("duration_ms", 0) // 1000,
            all_artists=all_artists,
            artist_id=artist_id,
            release_date=release_date,
            release_year=release_year,
            popularity=data.get("popularity"),
            explicit=data.get("explicit"),
            track_number=data.get("track_number"),
            album_art_url=album_art_url,
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

    def enrich_tracks(self, tracks: list[Track]) -> None:
        """Enrich tracks with audio features and artist genres (in-place)."""
        self._enrich_audio_features(tracks)
        self._enrich_artist_genres(tracks)

    def _enrich_audio_features(self, tracks: list[Track]) -> None:
        """Batch-fetch audio features and apply to tracks."""
        audio_feature_fields = [
            "tempo", "energy", "danceability", "valence", "acousticness",
            "instrumentalness", "loudness", "speechiness", "liveness",
            "key", "time_signature", "mode",
        ]

        for i in range(0, len(tracks), 100):
            batch = tracks[i : i + 100]
            ids = [t.id for t in batch]
            try:
                features_list = self._sp.audio_features(ids)
            except Exception:
                continue

            if not features_list:
                continue

            for track, features in zip(batch, features_list):
                if not features:
                    continue
                for field_name in audio_feature_fields:
                    if field_name in features:
                        setattr(track, field_name, features[field_name])

    def _enrich_artist_genres(self, tracks: list[Track]) -> None:
        """Batch-fetch artist genres and apply to tracks."""
        # Deduplicate by artist_id
        artist_to_tracks: dict[str, list[Track]] = {}
        for track in tracks:
            if track.artist_id:
                artist_to_tracks.setdefault(track.artist_id, []).append(track)

        unique_ids = list(artist_to_tracks.keys())

        for i in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[i : i + 50]
            try:
                result = self._sp.artists(batch_ids)
            except Exception:
                continue

            if not result or "artists" not in result:
                continue

            for artist_data in result["artists"]:
                if not artist_data:
                    continue
                aid = artist_data["id"]
                genres = artist_data.get("genres", [])
                for track in artist_to_tracks.get(aid, []):
                    track.genres = genres
