"""Tests for Spotify URL/URI parsing."""

import pytest

from spotifytoyoutube.spotify_url import SpotifyResource, parse_spotify_url


class TestParseSpotifyUrl:
    @pytest.mark.parametrize(
        ("raw", "kind", "id_"),
        [
            (
                "https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6",
                "track",
                "6rqhFgbbKwnb9MLmUQDhG6",
            ),
            (
                "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3",
                "album",
                "1DFixLWuPkv3KT3TnV35m3",
            ),
            (
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                "playlist",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            (
                "https://open.spotify.com/artist/4Z8W4fKeB5YxbusRsdQVPb",
                "artist",
                "4Z8W4fKeB5YxbusRsdQVPb",
            ),
            ("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", "track", "6rqhFgbbKwnb9MLmUQDhG6"),
            ("spotify:album:1DFixLWuPkv3KT3TnV35m3", "album", "1DFixLWuPkv3KT3TnV35m3"),
            ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "playlist", "37i9dQZF1DXcBWIGoYBM5M"),
            ("spotify:artist:4Z8W4fKeB5YxbusRsdQVPb", "artist", "4Z8W4fKeB5YxbusRsdQVPb"),
        ],
    )
    def test_parses_standard_forms(self, raw: str, kind: str, id_: str) -> None:
        resource = parse_spotify_url(raw)
        assert resource.kind == kind
        assert resource.id == id_

    def test_strips_intl_prefix(self) -> None:
        resource = parse_spotify_url(
            "https://open.spotify.com/intl-fr/track/6rqhFgbbKwnb9MLmUQDhG6"
        )
        assert resource.kind == "track"
        assert resource.id == "6rqhFgbbKwnb9MLmUQDhG6"

    def test_strips_query_string(self) -> None:
        resource = parse_spotify_url(
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abcdef"
        )
        assert resource.kind == "playlist"
        assert resource.id == "37i9dQZF1DXcBWIGoYBM5M"

    @pytest.mark.parametrize(
        "sentinel", ["liked", "LIKED", "liked-songs", "spotify:liked"]
    )
    def test_liked_sentinel(self, sentinel: str) -> None:
        resource = parse_spotify_url(sentinel)
        assert resource.kind == "liked"
        assert resource.id is None

    def test_strips_whitespace(self) -> None:
        resource = parse_spotify_url(
            "  https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6  "
        )
        assert resource.kind == "track"
        assert resource.id == "6rqhFgbbKwnb9MLmUQDhG6"

    def test_raises_on_unknown_url(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized Spotify"):
            parse_spotify_url("https://example.com/whatever")

    def test_raises_on_unknown_kind(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized Spotify"):
            parse_spotify_url("https://open.spotify.com/user/someuser")

    def test_raises_on_empty_input(self) -> None:
        with pytest.raises(ValueError):
            parse_spotify_url("")

    def test_raises_on_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            parse_spotify_url("   ")

    def test_raises_on_bad_uri(self) -> None:
        with pytest.raises(ValueError):
            parse_spotify_url("spotify:user:matt")


class TestSpotifyResource:
    def test_is_frozen_dataclass(self) -> None:
        resource = SpotifyResource(kind="track", id="abc")
        with pytest.raises(Exception):
            resource.kind = "album"  # type: ignore[misc]
