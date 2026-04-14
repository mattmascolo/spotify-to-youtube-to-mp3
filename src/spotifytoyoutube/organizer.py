"""Filesystem layout helpers for organized downloads."""

import re
from pathlib import Path

from spotifytoyoutube.spotify_client import Track

_FORBIDDEN = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def sanitize(value: str) -> str:
    """
    Sanitize a string for use as a filename or directory component.

    Strips characters forbidden on common filesystems, collapses whitespace,
    and trims trailing dots/spaces (Windows rejects these as path segments).
    Returns '_' when the input would otherwise yield an empty segment.
    """
    cleaned = _FORBIDDEN.sub(" ", value)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned or "_"


def build_path(track: Track, output_dir: Path, ext: str) -> Path:
    """
    Compute the organized destination path for a track.

    Layout: ``<output_dir>/<Artist>/<Album>/<NN> - <Title>.<ext>``

    Falls back to ``<Title>.<ext>`` when ``track_number`` is None. Track
    numbers are zero-padded to two digits for sensible sort order; larger
    numbers pass through unchanged.

    Pure function — no filesystem I/O.
    """
    suffix = ext if ext.startswith(".") else f".{ext}"

    artist_dir = sanitize(track.artist)
    album_dir = sanitize(track.album)
    title = sanitize(track.name)

    if track.track_number is not None:
        filename = f"{track.track_number:02d} - {title}{suffix}"
    else:
        filename = f"{title}{suffix}"

    return output_dir / artist_dir / album_dir / filename
