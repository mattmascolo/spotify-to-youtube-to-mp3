"""SoundCloud search via yt-dlp's scsearch: prefix.

Duck-typed to the same interface as YouTubeSearcher so TrackMatcher can
treat either source identically. Results are returned as YouTubeResult
instances with override_url set to the SoundCloud permalink.
"""

from typing import Any

import yt_dlp

from spotifytoyoutube.youtube_search import YouTubeResult


class SoundCloudSearcher:
    """Search SoundCloud for audio tracks using yt-dlp."""

    def __init__(self, quiet: bool = True) -> None:
        self.quiet = quiet

    def _get_ydl_opts(self) -> dict[str, Any]:
        return {
            "quiet": self.quiet,
            "no_warnings": self.quiet,
            "extract_flat": False,
            "skip_download": True,
            "ignoreerrors": True,
        }

    def search(self, query: str, max_results: int = 10) -> list[YouTubeResult]:
        """Search SoundCloud. Returns YouTubeResults with override_url set."""
        search_url = f"scsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(self._get_ydl_opts()) as ydl:
            try:
                info = ydl.extract_info(search_url, download=False)
            except Exception:
                return []

        if not info:
            return []

        results: list[YouTubeResult] = []
        for entry in info.get("entries", []) or []:
            if not entry:
                continue
            results.append(self._entry_to_result(entry))
        return results

    def get_video_info(self, track_id: str) -> YouTubeResult | None:
        """SoundCloud search entries already include full info; no refresh needed."""
        return None

    @staticmethod
    def _entry_to_result(entry: dict[str, Any]) -> YouTubeResult:
        return YouTubeResult(
            video_id=str(entry.get("id", "")),
            title=entry.get("title", ""),
            duration_seconds=int(entry.get("duration", 0) or 0),
            audio_bitrate=int(entry.get("abr") or 0),
            audio_codec=entry.get("acodec") or "unknown",
            description=entry.get("description"),
            override_url=entry.get("webpage_url") or entry.get("url"),
        )
