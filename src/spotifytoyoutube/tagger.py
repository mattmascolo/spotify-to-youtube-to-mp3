"""Embed Spotify metadata into downloaded audio files using mutagen."""

import base64
import logging
import struct
from pathlib import Path
from urllib.request import urlopen

from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPE1, TRCK
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus

from spotifytoyoutube.matcher import MatchResult

logger = logging.getLogger(__name__)

_album_art_cache: dict[str, bytes | None] = {}


def _download_album_art(url: str) -> bytes | None:
    """Download album art from Spotify CDN, with in-memory caching."""
    if url in _album_art_cache:
        return _album_art_cache[url]
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310
            data = resp.read()
        _album_art_cache[url] = data
        return data
    except Exception:
        logger.debug("Failed to download album art from %s", url)
        _album_art_cache[url] = None
        return None


def _tag_mp3(filepath: Path, match: MatchResult, album_art: bytes | None) -> None:
    """Write ID3v2 tags to an MP3 file."""
    track = match.track
    try:
        tags = ID3(filepath)
    except Exception:
        tags = ID3()

    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.delall("TALB")
    tags.delall("TDRC")
    tags.delall("TRCK")
    tags.delall("TCON")
    tags.delall("APIC")

    tags.add(TIT2(encoding=3, text=track.name))
    tags.add(TPE1(encoding=3, text=track.artist))
    tags.add(TALB(encoding=3, text=track.album))

    if track.release_year:
        tags.add(TDRC(encoding=3, text=str(track.release_year)))
    if track.track_number is not None:
        tags.add(TRCK(encoding=3, text=str(track.track_number)))
    if track.genres:
        tags.add(TCON(encoding=3, text=track.genres[0]))

    if album_art:
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # Cover (front)
                desc="Cover",
                data=album_art,
            )
        )

    tags.save(filepath)


def _tag_m4a(filepath: Path, match: MatchResult, album_art: bytes | None) -> None:
    """Write MP4/M4A tags."""
    track = match.track
    audio = MP4(filepath)

    audio.tags["\xa9nam"] = [track.name]
    audio.tags["\xa9ART"] = [track.artist]
    audio.tags["\xa9alb"] = [track.album]

    if track.release_year:
        audio.tags["\xa9day"] = [str(track.release_year)]
    if track.track_number is not None:
        audio.tags["trkn"] = [(track.track_number, 0)]
    if track.genres:
        audio.tags["\xa9gen"] = [track.genres[0]]

    if album_art:
        audio.tags["covr"] = [MP4Cover(album_art, imageformat=MP4Cover.FORMAT_JPEG)]

    audio.save()


def _make_flac_picture_block(image_data: bytes) -> str:
    """Build a base64-encoded FLAC METADATA_BLOCK_PICTURE for Vorbis comments."""
    # FLAC picture block format:
    # type(4) + mime_len(4) + mime + desc_len(4) + desc + width(4) + height(4)
    # + depth(4) + colors(4) + data_len(4) + data
    mime = b"image/jpeg"
    desc = b""
    block = struct.pack(">II", 3, len(mime)) + mime
    block += struct.pack(">I", len(desc)) + desc
    block += struct.pack(">IIII", 0, 0, 0, 0)  # width, height, depth, colors
    block += struct.pack(">I", len(image_data)) + image_data
    return base64.b64encode(block).decode("ascii")


def _tag_opus(filepath: Path, match: MatchResult, album_art: bytes | None) -> None:
    """Write Vorbis comments to an Opus file."""
    track = match.track
    audio = OggOpus(filepath)

    audio["title"] = [track.name]
    audio["artist"] = [track.artist]
    audio["album"] = [track.album]

    if track.release_year:
        audio["date"] = [str(track.release_year)]
    if track.track_number is not None:
        audio["tracknumber"] = [str(track.track_number)]
    if track.genres:
        audio["genre"] = [track.genres[0]]

    if album_art:
        audio["METADATA_BLOCK_PICTURE"] = [_make_flac_picture_block(album_art)]

    audio.save()


def _tag_wav(filepath: Path, match: MatchResult, album_art: bytes | None) -> None:
    """Best-effort ID3-in-WAV tagging (no album art)."""
    track = match.track
    try:
        tags = ID3(filepath)
    except Exception:
        tags = ID3()

    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.delall("TALB")
    tags.delall("TDRC")
    tags.delall("TRCK")
    tags.delall("TCON")

    tags.add(TIT2(encoding=3, text=track.name))
    tags.add(TPE1(encoding=3, text=track.artist))
    tags.add(TALB(encoding=3, text=track.album))

    if track.release_year:
        tags.add(TDRC(encoding=3, text=str(track.release_year)))
    if track.track_number is not None:
        tags.add(TRCK(encoding=3, text=str(track.track_number)))
    if track.genres:
        tags.add(TCON(encoding=3, text=track.genres[0]))

    tags.save(filepath)


_FORMAT_HANDLERS = {
    "mp3": _tag_mp3,
    "m4a": _tag_m4a,
    "opus": _tag_opus,
    "wav": _tag_wav,
}


def tag_file(filepath: Path, match: MatchResult, audio_format: str) -> bool:
    """
    Tag an audio file with Spotify metadata.

    Args:
        filepath: Path to the downloaded audio file
        match: MatchResult containing Spotify track metadata
        audio_format: Audio format string (mp3, m4a, opus, wav)

    Returns:
        True if tagging succeeded, False otherwise (file is kept untagged)
    """
    handler = _FORMAT_HANDLERS.get(audio_format)
    if not handler:
        logger.warning("No tagger for format %r, skipping tags", audio_format)
        return False

    album_art: bytes | None = None
    if match.track.album_art_url:
        album_art = _download_album_art(match.track.album_art_url)

    try:
        handler(filepath, match, album_art)
        return True
    except Exception:
        logger.warning("Failed to tag %s", filepath, exc_info=True)
        return False
