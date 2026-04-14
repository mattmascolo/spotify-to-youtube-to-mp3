"""Tests for Spotify client functionality."""

from unittest.mock import Mock

from spotifytoyoutube.spotify_client import PlaylistSummary, SpotifyClient, Track


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


class TestPlaylistSupport:
    """Tests for playlist listing and fetching."""

    def test_playlist_summary_from_api_response(self) -> None:
        data = {
            "id": "pl1",
            "name": "Road Trip",
            "owner": {"display_name": "Matt"},
            "tracks": {"total": 42},
            "public": True,
            "collaborative": False,
            "description": "bangers",
        }
        summary = PlaylistSummary.from_api_response(data)
        assert summary.id == "pl1"
        assert summary.name == "Road Trip"
        assert summary.owner == "Matt"
        assert summary.track_count == 42
        assert summary.public is True
        assert summary.collaborative is False
        assert summary.description == "bangers"

    def test_playlist_summary_handles_missing_fields(self) -> None:
        summary = PlaylistSummary.from_api_response({"id": "x"})
        assert summary.id == "x"
        assert summary.name == "Untitled"
        assert summary.owner == "Unknown"
        assert summary.track_count == 0
        assert summary.public is False
        assert summary.collaborative is False
        assert summary.description == ""

    def test_get_user_playlists_single_page(self) -> None:
        mock_sp = Mock()
        mock_sp.current_user_playlists.return_value = {
            "items": [
                {
                    "id": "pl1",
                    "name": "Road Trip",
                    "owner": {"display_name": "Matt"},
                    "tracks": {"total": 42},
                    "public": True,
                    "collaborative": False,
                    "description": "bangers",
                },
                {
                    "id": "pl2",
                    "name": "Chill",
                    "owner": {"display_name": "Matt"},
                    "tracks": {"total": 17},
                    "public": False,
                    "collaborative": True,
                    "description": "",
                },
            ],
            "next": None,
        }
        client = SpotifyClient(mock_sp)
        playlists = list(client.get_user_playlists())

        assert len(playlists) == 2
        assert playlists[0].id == "pl1"
        assert playlists[0].name == "Road Trip"
        assert playlists[0].owner == "Matt"
        assert playlists[0].track_count == 42
        assert playlists[0].public is True
        assert playlists[1].collaborative is True

    def test_get_user_playlists_pagination(self) -> None:
        def make_page(start: int, count: int, has_next: bool) -> dict:
            return {
                "items": [
                    {
                        "id": f"pl{i}",
                        "name": f"Playlist {i}",
                        "owner": {"display_name": "Matt"},
                        "tracks": {"total": 10},
                        "public": True,
                        "collaborative": False,
                        "description": "",
                    }
                    for i in range(start, start + count)
                ],
                "next": "https://api.spotify.com/next" if has_next else None,
            }

        mock_sp = Mock()
        mock_sp.current_user_playlists.side_effect = [
            make_page(0, 50, has_next=True),
            make_page(50, 1, has_next=False),
        ]
        client = SpotifyClient(mock_sp)
        playlists = list(client.get_user_playlists())
        assert len(playlists) == 51
        assert mock_sp.current_user_playlists.call_count == 2

    def test_get_user_playlists_skips_none_items(self) -> None:
        mock_sp = Mock()
        mock_sp.current_user_playlists.return_value = {
            "items": [
                None,
                {
                    "id": "pl1",
                    "name": "Chill",
                    "owner": {"display_name": "Matt"},
                    "tracks": {"total": 10},
                    "public": True,
                    "collaborative": False,
                    "description": "",
                },
            ],
            "next": None,
        }
        client = SpotifyClient(mock_sp)
        playlists = list(client.get_user_playlists())
        assert len(playlists) == 1
        assert playlists[0].id == "pl1"

    def test_get_playlist_tracks_skips_none_and_local(self) -> None:
        mock_sp = Mock()
        mock_sp.playlist_items.return_value = {
            "items": [
                {
                    "track": {
                        "id": "t1",
                        "name": "Good Song",
                        "artists": [{"name": "Artist"}],
                        "album": {"name": "Album"},
                        "duration_ms": 180000,
                    },
                    "is_local": False,
                },
                {"track": None, "is_local": False},
                {
                    "track": {
                        "id": "local1",
                        "name": "Local File",
                        "artists": [{"name": "Artist"}],
                        "album": {"name": "Album"},
                        "duration_ms": 180000,
                    },
                    "is_local": True,
                },
            ],
            "next": None,
        }
        client = SpotifyClient(mock_sp)
        tracks = list(client.get_playlist_tracks("pl1"))

        assert len(tracks) == 1
        assert tracks[0].id == "t1"
        mock_sp.playlist_items.assert_called_once_with(
            "pl1", limit=100, offset=0, additional_types=("track",)
        )

    def test_get_playlist_tracks_respects_max_tracks(self) -> None:
        mock_sp = Mock()
        mock_sp.playlist_items.return_value = {
            "items": [
                {
                    "track": {
                        "id": f"t{i}",
                        "name": f"Song {i}",
                        "artists": [{"name": "Artist"}],
                        "album": {"name": "Album"},
                        "duration_ms": 180000,
                    },
                    "is_local": False,
                }
                for i in range(100)
            ],
            "next": "https://api.spotify.com/next",
        }
        client = SpotifyClient(mock_sp)
        tracks = list(client.get_playlist_tracks("pl1", max_tracks=5))
        assert len(tracks) == 5

    def test_get_playlist_tracks_pagination(self) -> None:
        def make_page(start: int, count: int, has_next: bool) -> dict:
            return {
                "items": [
                    {
                        "track": {
                            "id": f"t{i}",
                            "name": f"Song {i}",
                            "artists": [{"name": "Artist"}],
                            "album": {"name": "Album"},
                            "duration_ms": 180000,
                        },
                        "is_local": False,
                    }
                    for i in range(start, start + count)
                ],
                "next": "https://api.spotify.com/next" if has_next else None,
            }

        mock_sp = Mock()
        mock_sp.playlist_items.side_effect = [
            make_page(0, 100, has_next=True),
            make_page(100, 20, has_next=False),
        ]
        client = SpotifyClient(mock_sp)
        tracks = list(client.get_playlist_tracks("pl1"))
        assert len(tracks) == 120
        assert mock_sp.playlist_items.call_count == 2


class TestAlbumArtistFetch:
    """Tests for album and artist track helpers."""

    def _make_full_track(self, idx: int) -> dict:
        return {
            "id": f"t{idx}",
            "name": f"Song {idx}",
            "artists": [{"name": "Artist", "id": "a1"}],
            "album": {"name": "Album", "images": [], "release_date": "2023"},
            "duration_ms": 180000,
        }

    def test_get_album_tracks_batches_through_tracks_api(self) -> None:
        mock_sp = Mock()
        mock_sp.album_tracks.return_value = {
            "items": [{"id": f"t{i}"} for i in range(3)],
            "next": None,
        }
        mock_sp.tracks.return_value = {
            "tracks": [self._make_full_track(i) for i in range(3)],
        }

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_album_tracks("alb1"))

        assert len(tracks) == 3
        assert all(t.artist == "Artist" for t in tracks)
        mock_sp.album_tracks.assert_called_once_with("alb1", limit=50, offset=0)
        mock_sp.tracks.assert_called_once_with(["t0", "t1", "t2"])

    def test_get_album_tracks_respects_max_tracks(self) -> None:
        mock_sp = Mock()
        mock_sp.album_tracks.return_value = {
            "items": [{"id": f"t{i}"} for i in range(20)],
            "next": None,
        }
        mock_sp.tracks.return_value = {
            "tracks": [self._make_full_track(i) for i in range(5)],
        }

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_album_tracks("alb1", max_tracks=5))

        assert len(tracks) == 5
        mock_sp.tracks.assert_called_once_with(["t0", "t1", "t2", "t3", "t4"])

    def test_get_album_tracks_skips_none_items(self) -> None:
        mock_sp = Mock()
        mock_sp.album_tracks.return_value = {
            "items": [{"id": "t0"}, None, {"id": "t1"}],
            "next": None,
        }
        mock_sp.tracks.return_value = {
            "tracks": [self._make_full_track(0), self._make_full_track(1)],
        }

        client = SpotifyClient(mock_sp)
        tracks = list(client.get_album_tracks("alb1"))

        assert len(tracks) == 2
        mock_sp.tracks.assert_called_once_with(["t0", "t1"])

    def test_get_artist_top_tracks(self) -> None:
        mock_sp = Mock()
        mock_sp.artist_top_tracks.return_value = {
            "tracks": [self._make_full_track(0)],
        }
        client = SpotifyClient(mock_sp)
        tracks = list(client.get_artist_top_tracks("a1"))
        assert len(tracks) == 1
        assert tracks[0].name == "Song 0"
        mock_sp.artist_top_tracks.assert_called_once_with("a1", country="US")

    def test_get_artist_top_tracks_custom_country(self) -> None:
        mock_sp = Mock()
        mock_sp.artist_top_tracks.return_value = {"tracks": []}
        client = SpotifyClient(mock_sp)
        list(client.get_artist_top_tracks("a1", country="GB"))
        mock_sp.artist_top_tracks.assert_called_once_with("a1", country="GB")
