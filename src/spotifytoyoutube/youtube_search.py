"""YouTube search functionality using yt-dlp."""

from dataclasses import dataclass
from typing import Any

import yt_dlp


@dataclass
class YouTubeResult:
    """Represents a YouTube search result with audio quality metadata."""

    video_id: str
    title: str
    duration_seconds: int
    audio_bitrate: int
    audio_codec: str

    @classmethod
    def from_yt_dlp_info(cls, info: dict[str, Any]) -> "YouTubeResult":
        """
        Create YouTubeResult from yt-dlp info dictionary.

        Args:
            info: Video info dict from yt-dlp

        Returns:
            YouTubeResult instance
        """
        # Try to get bitrate from top-level, otherwise extract from formats
        audio_bitrate = info.get("abr") or 0
        audio_codec = info.get("acodec") or "unknown"

        if not audio_bitrate:
            # Extract best audio bitrate from formats list
            formats = info.get("formats", [])
            audio_formats = [
                f for f in formats
                if f.get("acodec") and f.get("acodec") != "none"
                and (not f.get("vcodec") or f.get("vcodec") == "none")
            ]
            if audio_formats:
                best = max(audio_formats, key=lambda f: f.get("abr") or 0)
                audio_bitrate = best.get("abr") or 0
                audio_codec = best.get("acodec") or "unknown"

        return cls(
            video_id=info.get("id", ""),
            title=info.get("title", ""),
            duration_seconds=info.get("duration", 0) or 0,
            audio_bitrate=int(audio_bitrate),
            audio_codec=audio_codec,
        )

    @property
    def url(self) -> str:
        """Return full YouTube URL."""
        return f"https://www.youtube.com/watch?v={self.video_id}"


class YouTubeSearcher:
    """Search YouTube for videos using yt-dlp."""

    def __init__(self, quiet: bool = True) -> None:
        """
        Initialize YouTube searcher.

        Args:
            quiet: Suppress yt-dlp output
        """
        self.quiet = quiet

    def _get_ydl_opts(self) -> dict[str, Any]:
        """Get yt-dlp options for searching."""
        return {
            "quiet": self.quiet,
            "no_warnings": self.quiet,
            "extract_flat": False,
            "skip_download": True,
            "ignoreerrors": True,
        }

    def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[YouTubeResult]:
        """
        Search YouTube for videos matching query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of YouTubeResult objects
        """
        search_url = f"ytsearch{max_results}:{query}"

        with yt_dlp.YoutubeDL(self._get_ydl_opts()) as ydl:
            try:
                info = ydl.extract_info(search_url, download=False)
            except Exception:
                return []

        if not info:
            return []

        entries = info.get("entries", [])
        results = []

        for entry in entries:
            if entry:
                results.append(YouTubeResult.from_yt_dlp_info(entry))

        return results

    def get_video_info(self, video_id: str) -> YouTubeResult | None:
        """
        Get detailed info for a specific video.

        Args:
            video_id: YouTube video ID

        Returns:
            YouTubeResult with full audio info, or None if not found
        """
        url = f"https://www.youtube.com/watch?v={video_id}"

        with yt_dlp.YoutubeDL(self._get_ydl_opts()) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception:
                return None

        if not info:
            return None

        # Get best audio format info
        formats = info.get("formats", [])
        best_audio = self._get_best_audio_format(formats)

        if best_audio:
            info["abr"] = best_audio.get("abr", 0)
            info["acodec"] = best_audio.get("acodec", "unknown")

        return YouTubeResult.from_yt_dlp_info(info)

    def _get_best_audio_format(
        self, formats: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Find the best audio format from available formats.

        Args:
            formats: List of format dicts from yt-dlp

        Returns:
            Best audio format dict, or None
        """
        audio_formats = [
            f for f in formats
            if f.get("acodec") and f.get("acodec") != "none"
            and (not f.get("vcodec") or f.get("vcodec") == "none")
        ]

        if not audio_formats:
            return None

        # Sort by bitrate descending
        return max(audio_formats, key=lambda f: f.get("abr", 0) or 0)
