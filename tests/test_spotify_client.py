"""Tests for Spotify client functionality."""

import pytest
from unittest.mock import Mock

from spotifytoyoutube.spotify_client import SpotifyClient, Track


class TestTrack:
    """Tests for Track dataclass."""

    def test_track_from_api_response(self, sample_spotify_track: dict) -> None:
        """Track can be created from Spotify API response."""
        track = Track.from_api_response(sample_spotify_track["track"])

        assert track.id == "abc123"
        assert track.name == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.duration_seconds == 180

    def test_track_search_query(self) -> None:
        """Track generates appropriate YouTube search query."""
        track = Track(
            id="123",
            name="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_seconds=180,
        )
        assert track.search_query == "Test Artist - Test Song"


class TestSpotifyClient:
    """Tests for SpotifyClient class."""

    def test_init_with_authenticated_client(self) -> None:
        """SpotifyClient accepts an authenticated spotipy instance."""
        mock_sp = Mock()
        client = SpotifyClient(mock_sp)
        assert client._sp == mock_sp

    def test_get_liked_songs_single_page(self) -> None:
        """get_liked_songs fetches tracks from a single page."""
        mock_sp = Mock()
        mock_sp.current_user_saved_tracks.return_value = {
            "items": [
                {
                    "track": {
                        "id": "track1",
                        "name": "Song 1",
                        "artists": [{"name": "Artist 1"}],
                        "album": {"name": "Album 1"},
                        "duration_ms": 180000,
                    }
                }
            ],
            "next": None,
        }

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_liked_songs(limit=50))

        assert len(tracks) == 1
        assert tracks[0].name == "Song 1"
        mock_sp.current_user_saved_tracks.assert_called_once_with(limit=50, offset=0)

    def test_get_liked_songs_pagination(self) -> None:
        """get_liked_songs handles pagination correctly."""
        mock_sp = Mock()

        # First page
        page1 = {
            "items": [
                {
                    "track": {
                        "id": f"track{i}",
                        "name": f"Song {i}",
                        "artists": [{"name": f"Artist {i}"}],
                        "album": {"name": f"Album {i}"},
                        "duration_ms": 180000,
                    }
                }
                for i in range(50)
            ],
            "next": "https://api.spotify.com/v1/me/tracks?offset=50",
        }

        # Second page
        page2 = {
            "items": [
                {
                    "track": {
                        "id": "track50",
                        "name": "Song 50",
                        "artists": [{"name": "Artist 50"}],
                        "album": {"name": "Album 50"},
                        "duration_ms": 180000,
                    }
                }
            ],
            "next": None,
        }

        mock_sp.current_user_saved_tracks.side_effect = [page1, page2]

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_liked_songs(limit=50))

        assert len(tracks) == 51
        assert mock_sp.current_user_saved_tracks.call_count == 2

    def test_get_liked_songs_max_tracks(self) -> None:
        """get_liked_songs respects max_tracks parameter."""
        mock_sp = Mock()
        mock_sp.current_user_saved_tracks.return_value = {
            "items": [
                {
                    "track": {
                        "id": f"track{i}",
                        "name": f"Song {i}",
                        "artists": [{"name": f"Artist {i}"}],
                        "album": {"name": f"Album {i}"},
                        "duration_ms": 180000,
                    }
                }
                for i in range(50)
            ],
            "next": "https://api.spotify.com/v1/me/tracks?offset=50",
        }

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_liked_songs(limit=50, max_tracks=10))

        assert len(tracks) == 10
