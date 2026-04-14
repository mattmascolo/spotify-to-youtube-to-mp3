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
    album_artist: str | None = None
    genres: list[str] | None = None
    release_date: str | None = None
    release_year: int | None = None
    popularity: int | None = None
    explicit: bool | None = None
    track_number: int | None = None
    disc_number: int | None = None
    album_art_url: str | None = None
    isrc: str | None = None

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

        album_artists = album.get("artists") or []
        album_artist = album_artists[0]["name"] if album_artists else None

        release_date = album.get("release_date")
        release_year = None
        if release_date:
            try:
                release_year = int(release_date[:4])
            except (ValueError, IndexError):
                pass

        external_ids = data.get("external_ids") or {}
        isrc = external_ids.get("isrc")

        return cls(
            id=data["id"],
            name=data["name"],
            artist=artist_name,
            album=album.get("name", "Unknown Album"),
            duration_seconds=data.get("duration_ms", 0) // 1000,
            all_artists=all_artists,
            artist_id=artist_id,
            album_artist=album_artist,
            release_date=release_date,
            release_year=release_year,
            popularity=data.get("popularity"),
            explicit=data.get("explicit"),
            track_number=data.get("track_number"),
            disc_number=data.get("disc_number"),
            album_art_url=album_art_url,
            isrc=isrc,
        )

    @property
    def search_query(self) -> str:
        """Generate YouTube search query for this track."""
        return f"{self.artist} - {self.name}"


@dataclass
class PlaylistSummary:
    """Lightweight summary of a Spotify playlist for listing / selection."""

    id: str
    name: str
    owner: str
    track_count: int
    public: bool
    collaborative: bool
    description: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "PlaylistSummary":
        return cls(
            id=data["id"],
            name=data.get("name") or "Untitled",
            owner=(data.get("owner") or {}).get("display_name") or "Unknown",
            track_count=(data.get("tracks") or {}).get("total", 0),
            public=bool(data.get("public")),
            collaborative=bool(data.get("collaborative")),
            description=data.get("description") or "",
        )


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

    def get_user_playlists(
        self,
        limit: int = 50,
    ) -> Iterator[PlaylistSummary]:
        """
        Yield all playlists owned or followed by the authenticated user.

        Args:
            limit: Page size for each API request (max 50)

        Yields:
            PlaylistSummary instances
        """
        offset = 0
        while True:
            response = self._sp.current_user_playlists(limit=limit, offset=offset)
            items = response.get("items", [])
            if not items:
                break

            for item in items:
                if item:
                    yield PlaylistSummary.from_api_response(item)

            if not response.get("next"):
                break
            offset += limit

    def get_playlist_tracks(
        self,
        playlist_id: str,
        limit: int = 100,
        max_tracks: int | None = None,
    ) -> Iterator[Track]:
        """
        Yield tracks from a specific playlist, skipping local / None entries.

        Args:
            playlist_id: Spotify playlist ID
            limit: Page size for each API request (max 100)
            max_tracks: Maximum total tracks to yield (None for all)

        Yields:
            Track instances
        """
        offset = 0
        fetched = 0
        while True:
            response = self._sp.playlist_items(
                playlist_id,
                limit=limit,
                offset=offset,
                additional_types=("track",),
            )
            items = response.get("items", [])
            if not items:
                break

            for item in items:
                if item.get("is_local"):
                    continue
                track_data = item.get("track")
                if not track_data:
                    continue
                yield Track.from_api_response(track_data)
                fetched += 1
                if max_tracks and fetched >= max_tracks:
                    return

            if not response.get("next"):
                break
            offset += limit

    def get_album_tracks(
        self,
        album_id: str,
        max_tracks: int | None = None,
    ) -> Iterator[Track]:
        """
        Yield full Track objects for every track on an album.

        Uses album_tracks to discover track IDs, then batches sp.tracks()
        calls so the resulting Track objects carry full album metadata.
        """
        offset = 0
        track_ids: list[str] = []
        while True:
            response = self._sp.album_tracks(album_id, limit=50, offset=offset)
            items = response.get("items", [])
            if not items:
                break
            for item in items:
                if not item:
                    continue
                tid = item.get("id")
                if not tid:
                    continue
                track_ids.append(tid)
                if max_tracks and len(track_ids) >= max_tracks:
                    break
            if max_tracks and len(track_ids) >= max_tracks:
                break
            if not response.get("next"):
                break
            offset += 50

        for i in range(0, len(track_ids), 50):
            batch = track_ids[i : i + 50]
            result = self._sp.tracks(batch)
            for track_data in result.get("tracks", []):
                if track_data:
                    yield Track.from_api_response(track_data)

    def get_artist_top_tracks(
        self,
        artist_id: str,
        country: str = "US",
    ) -> Iterator[Track]:
        """Yield the artist's top tracks for a given market (up to 10)."""
        response = self._sp.artist_top_tracks(artist_id, country=country)
        for track_data in response.get("tracks", []):
            if track_data:
                yield Track.from_api_response(track_data)

    def enrich_tracks(self, tracks: list[Track]) -> None:
        """Enrich tracks with audio features and artist genres (in-place)."""
        self._enrich_audio_features(tracks)
        self._enrich_artist_genres(tracks)

    def _enrich_audio_features(self, tracks: list[Track]) -> None:
        """
        Batch-fetch audio features and apply to tracks.

        Spotify restricted audio-features to user-auth tokens (and newer apps
        may not have access at all), so this is best-effort: any failure is
        logged to the spotipy logger and otherwise swallowed so it doesn't
        break the match pipeline.
        """
        import logging

        audio_feature_fields = [
            "tempo", "energy", "danceability", "valence", "acousticness",
            "instrumentalness", "loudness", "speechiness", "liveness",
            "key", "time_signature", "mode",
        ]

        spotipy_logger = logging.getLogger("spotipy.client")
        prior_level = spotipy_logger.level
        spotipy_logger.setLevel(logging.CRITICAL)
        try:
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
        finally:
            spotipy_logger.setLevel(prior_level)

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
