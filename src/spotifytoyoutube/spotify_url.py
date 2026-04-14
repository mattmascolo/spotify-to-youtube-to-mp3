"""Parse Spotify web URLs and URIs into structured resource references."""

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

ResourceKind = Literal["track", "album", "playlist", "artist", "liked"]

_VALID_KINDS: frozenset[str] = frozenset({"track", "album", "playlist", "artist"})
_LIKED_SENTINELS: frozenset[str] = frozenset({"liked", "liked-songs", "spotify:liked"})
_INTL_PREFIX = re.compile(r"^intl-[a-z]{2}$", re.IGNORECASE)


@dataclass(frozen=True)
class SpotifyResource:
    """A parsed Spotify resource reference."""

    kind: ResourceKind
    id: str | None


def parse_spotify_url(raw: str) -> SpotifyResource:
    """
    Parse a Spotify URL, URI, or 'liked' sentinel into a SpotifyResource.

    Accepts:
        - https://open.spotify.com/<kind>/<id>
        - https://open.spotify.com/intl-xx/<kind>/<id>
        - spotify:<kind>:<id>
        - 'liked', 'liked-songs', 'spotify:liked' (case-insensitive)

    Raises:
        ValueError: on empty, whitespace-only, or unrecognized input.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty Spotify URL")

    normalized = raw.strip()

    if normalized.lower() in _LIKED_SENTINELS:
        return SpotifyResource(kind="liked", id=None)

    if normalized.lower().startswith("spotify:"):
        parts = normalized.split(":")
        if len(parts) >= 3 and parts[1].lower() in _VALID_KINDS:
            kind: ResourceKind = parts[1].lower()  # type: ignore[assignment]
            return SpotifyResource(kind=kind, id=parts[2])
        raise ValueError(f"Unrecognized Spotify URI: {raw}")

    parsed = urlparse(normalized)
    if parsed.hostname and "spotify.com" in parsed.hostname:
        segments = [s for s in parsed.path.split("/") if s]
        if segments and _INTL_PREFIX.match(segments[0]):
            segments = segments[1:]
        if len(segments) >= 2 and segments[0].lower() in _VALID_KINDS:
            kind = segments[0].lower()  # type: ignore[assignment]
            return SpotifyResource(kind=kind, id=segments[1])

    raise ValueError(f"Unrecognized Spotify URL: {raw}")
