"""Export functionality for match results."""

import csv
import json
from datetime import datetime
from pathlib import Path

from spotifytoyoutube.matcher import MatchResult


def export_to_json(matches: list[MatchResult], output_path: Path) -> None:
    """
    Export matches to JSON format.

    Args:
        matches: List of MatchResult objects
        output_path: Path to output JSON file
    """
    data = {
        "generated_at": datetime.now().isoformat(),
        "total_matches": len(matches),
        "matches": [
            {
                "spotify_track": {
                    "name": m.track.name,
                    "artist": m.track.artist,
                    "album": m.track.album,
                    "duration_seconds": m.track.duration_seconds,
                },
                "youtube_url": m.youtube_result.url,
                "youtube_title": m.youtube_result.title,
                "audio_bitrate": m.audio_bitrate,
                "title_similarity": round(m.title_similarity, 3),
                "duration_match": m.duration_match,
            }
            for m in matches
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_to_csv(matches: list[MatchResult], output_path: Path) -> None:
    """
    Export matches to CSV format.

    Args:
        matches: List of MatchResult objects
        output_path: Path to output CSV file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "artist",
        "song",
        "album",
        "spotify_duration",
        "youtube_url",
        "youtube_title",
        "audio_bitrate",
        "title_similarity",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for m in matches:
            writer.writerow({
                "artist": m.track.artist,
                "song": m.track.name,
                "album": m.track.album,
                "spotify_duration": m.track.duration_seconds,
                "youtube_url": m.youtube_result.url,
                "youtube_title": m.youtube_result.title,
                "audio_bitrate": m.audio_bitrate,
                "title_similarity": round(m.title_similarity, 3),
            })


def export_to_m3u(matches: list[MatchResult], output_path: Path) -> None:
    """
    Export matches to M3U playlist format.

    Args:
        matches: List of MatchResult objects
        output_path: Path to output M3U file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")

        for m in matches:
            # EXTINF format: duration, artist - title
            f.write(f"#EXTINF:{m.track.duration_seconds},{m.track.artist} - {m.track.name}\n")
            f.write(f"{m.youtube_result.url}\n")


def _export_to_txt(matches: list[MatchResult], output_path: Path) -> None:
    """Export matches as plain text URLs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(m.youtube_result.url for m in matches))


class Exporter:
    """Export manager that auto-detects format from file extension."""

    FORMAT_HANDLERS = {
        ".json": export_to_json,
        ".csv": export_to_csv,
        ".m3u": export_to_m3u,
        ".m3u8": export_to_m3u,
        ".txt": _export_to_txt,
    }

    def export(
        self,
        matches: list[MatchResult],
        output_path: Path,
        format_override: str | None = None,
    ) -> None:
        """
        Export matches to file, auto-detecting format from extension.

        Args:
            matches: List of MatchResult objects
            output_path: Path to output file
            format_override: Force specific format (e.g., "json", "csv")

        Raises:
            ValueError: If format cannot be determined or is unsupported
        """
        if format_override:
            ext = f".{format_override.lower().lstrip('.')}"
        else:
            ext = output_path.suffix.lower()

        handler = self.FORMAT_HANDLERS.get(ext)
        if not handler:
            supported = ", ".join(self.FORMAT_HANDLERS.keys())
            raise ValueError(f"Unsupported format: {ext}. Supported: {supported}")

        handler(matches, output_path)

    @classmethod
    def supported_formats(cls) -> list[str]:
        """Return list of supported export formats."""
        return list(cls.FORMAT_HANDLERS.keys())
