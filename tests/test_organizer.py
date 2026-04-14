"""Tests for the filesystem organizer."""

from pathlib import Path
from typing import Any

from spotifytoyoutube.organizer import build_path, sanitize
from spotifytoyoutube.spotify_client import Track


def make_track(**overrides: Any) -> Track:
    base: dict[str, Any] = dict(
        id="sp1",
        name="Test Song",
        artist="Test Artist",
        album="Test Album",
        duration_seconds=180,
        track_number=3,
    )
    base.update(overrides)
    return Track(**base)


class TestSanitize:
    def test_removes_forbidden_characters(self) -> None:
        cleaned = sanitize('a/b\\c:d*e?f"g<h>i|j')
        for ch in '/\\:*?"<>|':
            assert ch not in cleaned

    def test_collapses_whitespace(self) -> None:
        assert sanitize("  hello   world  ") == "hello world"

    def test_preserves_unicode(self) -> None:
        assert sanitize("Björk - Jóga") == "Björk - Jóga"

    def test_empty_string_becomes_underscore(self) -> None:
        assert sanitize("") == "_"

    def test_whitespace_only_becomes_underscore(self) -> None:
        assert sanitize("   ") == "_"

    def test_dots_at_end_stripped(self) -> None:
        assert sanitize("Hello...") == "Hello"

    def test_trailing_spaces_stripped(self) -> None:
        assert sanitize("Hello   ") == "Hello"


class TestBuildPath:
    def test_standard_track(self, tmp_path: Path) -> None:
        track = make_track()
        path = build_path(track, tmp_path, "mp3")
        assert path == tmp_path / "Test Artist" / "Test Album" / "03 - Test Song.mp3"

    def test_missing_track_number_omits_prefix(self, tmp_path: Path) -> None:
        track = make_track(track_number=None)
        path = build_path(track, tmp_path, "mp3")
        assert path == tmp_path / "Test Artist" / "Test Album" / "Test Song.mp3"

    def test_sanitizes_path_segments(self, tmp_path: Path) -> None:
        track = make_track(
            artist="AC/DC",
            album="Back: In/Black",
            name='Song "With" <Quotes>',
        )
        path = build_path(track, tmp_path, "mp3")
        parts = path.relative_to(tmp_path).parts
        assert "/" not in parts[0]
        assert ":" not in parts[1]
        assert '"' not in parts[2]

    def test_zero_pads_track_number(self, tmp_path: Path) -> None:
        track = make_track(track_number=7)
        path = build_path(track, tmp_path, "mp3")
        assert "07 - " in path.name

    def test_large_track_numbers_not_truncated(self, tmp_path: Path) -> None:
        track = make_track(track_number=123)
        path = build_path(track, tmp_path, "mp3")
        assert "123 - " in path.name

    def test_respects_ext_with_dot(self, tmp_path: Path) -> None:
        track = make_track()
        assert build_path(track, tmp_path, ".mp3").suffix == ".mp3"

    def test_respects_ext_without_dot(self, tmp_path: Path) -> None:
        track = make_track()
        assert build_path(track, tmp_path, "opus").suffix == ".opus"

    def test_returns_pure_path_no_io(self, tmp_path: Path) -> None:
        """build_path must not create directories — pure function."""
        track = make_track()
        path = build_path(track, tmp_path, "mp3")
        assert not path.parent.exists()
        assert not path.exists()
