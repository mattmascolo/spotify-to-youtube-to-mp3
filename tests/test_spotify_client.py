"""Tests for Spotify client functionality."""

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

        # Extended metadata
        assert track.all_artists == ["Test Artist", "Featured Artist"]
        assert track.artist_id == "artist1"
        assert track.release_date == "2023-06-15"
        assert track.release_year == 2023
        assert track.popularity == 75
        assert track.explicit is False
        assert track.track_number == 3
        assert track.album_art_url == "https://i.scdn.co/image/abc123"

        # Audio features not yet enriched
        assert track.tempo is None
        assert track.genres is None

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

    def test_enrich_audio_features(self) -> None:
        """_enrich_audio_features applies features to tracks."""
        mock_sp = Mock()
        mock_sp.audio_features.return_value = [
            {
                "id": "t1",
                "tempo": 120.0,
                "energy": 0.8,
                "danceability": 0.7,
                "valence": 0.6,
                "acousticness": 0.1,
                "instrumentalness": 0.0,
                "loudness": -5.0,
                "speechiness": 0.05,
                "liveness": 0.1,
                "key": 5,
                "time_signature": 4,
                "mode": 1,
            },
        ]

        track = Track(id="t1", name="Song", artist="Artist", album="Album", duration_seconds=180)
        client = SpotifyClient(mock_sp)
        client._enrich_audio_features([track])

        assert track.tempo == 120.0
        assert track.energy == 0.8
        assert track.danceability == 0.7
        assert track.key == 5
        assert track.time_signature == 4
        mock_sp.audio_features.assert_called_once_with(["t1"])

    def test_enrich_artist_genres(self) -> None:
        """_enrich_artist_genres applies genres from artist lookup."""
        mock_sp = Mock()
        mock_sp.artists.return_value = {
            "artists": [
                {"id": "a1", "genres": ["pop", "indie pop"]},
            ],
        }

        t1 = Track(
            id="t1", name="Song 1", artist="Artist", album="Album",
            duration_seconds=180, artist_id="a1",
        )
        t2 = Track(
            id="t2", name="Song 2", artist="Artist", album="Album",
            duration_seconds=200, artist_id="a1",
        )
        client = SpotifyClient(mock_sp)
        client._enrich_artist_genres([t1, t2])

        assert t1.genres == ["pop", "indie pop"]
        assert t2.genres == ["pop", "indie pop"]
        # Should deduplicate: only one call for the same artist
        mock_sp.artists.assert_called_once_with(["a1"])

    def test_enrich_tracks_calls_both(self) -> None:
        """enrich_tracks calls both audio features and artist genres."""
        mock_sp = Mock()
        mock_sp.audio_features.return_value = [None]
        mock_sp.artists.return_value = {"artists": []}

        track = Track(
            id="t1", name="Song", artist="Artist", album="Album",
            duration_seconds=180, artist_id="a1",
        )
        client = SpotifyClient(mock_sp)
        client.enrich_tracks([track])

        mock_sp.audio_features.assert_called_once()
        mock_sp.artists.assert_called_once()
