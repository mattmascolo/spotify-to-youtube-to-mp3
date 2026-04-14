"""Tests for the metadata tagger module."""

from pathlib import Path
from unittest.mock import patch

import pytest
from mutagen.id3 import ID3

from spotifytoyoutube.matcher import MatchResult
from spotifytoyoutube.tagger import (
    _album_art_cache,
    _download_album_art,
    tag_file,
)


@pytest.fixture(autouse=True)
def _clear_art_cache():
    """Clear album art cache between tests."""
    _album_art_cache.clear()
    yield
    _album_art_cache.clear()


def _make_minimal_mp3(path: Path) -> None:
    """Create a minimal valid MP3 file for testing."""
    # Minimal MP3 frame: sync word + header
    # MPEG1 Layer3 128kbps 44100Hz stereo
    header = b"\xff\xfb\x90\x00"
    # A frame at 128kbps, 44100Hz is 417 bytes
    frame = header + b"\x00" * 413
    path.write_bytes(frame * 3)


class TestTagFile:
    """Tests for the tag_file function."""

    def test_returns_false_for_unsupported_format(self, sample_match_result: MatchResult) -> None:
        """tag_file returns False for unsupported audio formats."""
        result = tag_file(Path("/tmp/fake.flac"), sample_match_result, "flac")
        assert result is False

    def test_returns_false_for_unknown_format(self, sample_match_result: MatchResult) -> None:
        """tag_file returns False for unknown format strings."""
        result = tag_file(Path("/tmp/fake.xyz"), sample_match_result, "xyz")
        assert result is False

    def test_dispatches_to_mp3_handler(
        self, tmp_path: Path, sample_match_result: MatchResult,
    ) -> None:
        """tag_file calls the mp3 handler for mp3 format."""
        mp3_path = tmp_path / "test.mp3"
        _make_minimal_mp3(mp3_path)

        with patch("spotifytoyoutube.tagger._download_album_art", return_value=None):
            result = tag_file(mp3_path, sample_match_result, "mp3")

        assert result is True

        # Verify tags were written
        tags = ID3(mp3_path)
        assert str(tags["TIT2"]) == "Test Song"
        assert str(tags["TPE1"]) == "Test Artist"
        assert str(tags["TPE2"]) == "Test Album Artist"
        assert str(tags["TALB"]) == "Test Album"
        assert str(tags["TDRC"]) == "2023"
        assert str(tags["TRCK"]) == "3"
        assert str(tags["TPOS"]) == "2"
        assert str(tags["TCON"]) == "indie pop"

    def test_handles_missing_album_art_url(
        self, tmp_path: Path, sample_match_result: MatchResult,
    ) -> None:
        """tag_file works when track has no album_art_url."""
        sample_match_result.track.album_art_url = None

        mp3_path = tmp_path / "test.mp3"
        _make_minimal_mp3(mp3_path)

        result = tag_file(mp3_path, sample_match_result, "mp3")
        assert result is True

        tags = ID3(mp3_path)
        assert str(tags["TIT2"]) == "Test Song"
        # No APIC frame
        assert "APIC:" not in tags and "APIC:Cover" not in tags

    def test_handles_missing_optional_fields(
        self, tmp_path: Path, sample_match_result: MatchResult,
    ) -> None:
        """tag_file works when optional track fields are None."""
        sample_match_result.track.release_year = None
        sample_match_result.track.track_number = None
        sample_match_result.track.disc_number = None
        sample_match_result.track.album_artist = None
        sample_match_result.track.genres = None
        sample_match_result.track.album_art_url = None

        mp3_path = tmp_path / "test.mp3"
        _make_minimal_mp3(mp3_path)

        result = tag_file(mp3_path, sample_match_result, "mp3")
        assert result is True

        tags = ID3(mp3_path)
        assert str(tags["TIT2"]) == "Test Song"
        # Album artist falls back to track artist when missing
        assert str(tags["TPE2"]) == "Test Artist"
        assert "TDRC" not in tags
        assert "TRCK" not in tags
        assert "TPOS" not in tags
        assert "TCON" not in tags

    def test_mp3_with_album_art(self, tmp_path: Path, sample_match_result: MatchResult) -> None:
        """tag_file embeds album art in MP3 files."""
        mp3_path = tmp_path / "test.mp3"
        _make_minimal_mp3(mp3_path)

        fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Minimal JPEG-like bytes
        with patch("spotifytoyoutube.tagger._download_album_art", return_value=fake_image):
            result = tag_file(mp3_path, sample_match_result, "mp3")

        assert result is True

        tags = ID3(mp3_path)
        apic = tags.getall("APIC")
        assert len(apic) == 1
        assert apic[0].data == fake_image
        assert apic[0].mime == "image/jpeg"

    def test_returns_false_on_tagging_error(self, sample_match_result: MatchResult) -> None:
        """tag_file returns False when the handler raises an exception."""
        from spotifytoyoutube.tagger import _FORMAT_HANDLERS

        def _raise(*args):
            raise OSError("disk full")

        original = _FORMAT_HANDLERS["mp3"]
        _FORMAT_HANDLERS["mp3"] = _raise
        try:
            result = tag_file(Path("/tmp/fake.mp3"), sample_match_result, "mp3")
            assert result is False
        finally:
            _FORMAT_HANDLERS["mp3"] = original


class TestDownloadAlbumArt:
    """Tests for album art downloading."""

    def test_caches_successful_download(self) -> None:
        """Downloaded album art is cached."""
        fake_image = b"\xff\xd8\xff\xe0JFIF"
        url = "https://i.scdn.co/image/test123"

        with patch("spotifytoyoutube.tagger.urlopen") as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = fake_image

            result = _download_album_art(url)
            assert result == fake_image

            # Second call should use cache (urlopen not called again)
            result2 = _download_album_art(url)
            assert result2 == fake_image
            assert mock_urlopen.call_count == 1

    def test_caches_failed_download(self) -> None:
        """Failed downloads are cached as None to avoid retries."""
        url = "https://i.scdn.co/image/fail"

        with patch("spotifytoyoutube.tagger.urlopen", side_effect=Exception("Network error")):
            result = _download_album_art(url)
            assert result is None

        assert _album_art_cache[url] is None

    def test_returns_cached_value(self) -> None:
        """Returns cached value without making a network request."""
        url = "https://i.scdn.co/image/cached"
        cached_data = b"cached_image_data"
        _album_art_cache[url] = cached_data

        with patch("spotifytoyoutube.tagger.urlopen") as mock_urlopen:
            result = _download_album_art(url)
            assert result == cached_data
            mock_urlopen.assert_not_called()
