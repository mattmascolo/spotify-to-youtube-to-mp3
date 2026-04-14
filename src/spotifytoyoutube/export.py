"""Export functionality for match results."""

import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from spotifytoyoutube.matcher import MatchResult
from spotifytoyoutube.spotify_client import Track
from spotifytoyoutube.youtube_search import YouTubeResult


def _video_id_from_url(url: str) -> str:
    """Extract YouTube video ID from a URL."""
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        return parse_qs(parsed.query).get("v", [""])[0]
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")
    return ""


def load_matches_from_json(path: Path) -> list[MatchResult]:
    """Reconstruct MatchResult objects from a previously exported JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    results: list[MatchResult] = []
    for entry in data.get("matches", []):
        st = entry.get("spotify_track", {})
        track = Track(
            id="",
            name=st.get("name", ""),
            artist=st.get("artist", ""),
            album=st.get("album", ""),
            duration_seconds=st.get("duration_seconds", 0),
            all_artists=st.get("all_artists"),
            genres=st.get("genres"),
            release_date=st.get("release_date"),
            release_year=st.get("release_year"),
            popularity=st.get("popularity"),
            explicit=st.get("explicit"),
            track_number=st.get("track_number"),
            album_art_url=st.get("album_art_url"),
        )

        yt_url = entry.get("youtube_url", "")
        video_id = _video_id_from_url(yt_url)
        yt_result = YouTubeResult(
            video_id=video_id,
            title=entry.get("youtube_title", ""),
            duration_seconds=track.duration_seconds,
            audio_bitrate=entry.get("audio_bitrate", 0),
            audio_codec="unknown",
        )

        results.append(MatchResult(
            track=track,
            youtube_result=yt_result,
            title_similarity=entry.get("title_similarity", 0),
            duration_match=entry.get("duration_match", False),
            audio_bitrate=entry.get("audio_bitrate", 0),
        ))

    return results


def _build_audio_features(track) -> dict | None:
    """Build audio_features dict from track, returning None if all values are None."""
    keys = [
        "tempo", "energy", "danceability", "valence", "acousticness",
        "instrumentalness", "loudness", "speechiness", "liveness",
        "key", "time_signature", "mode",
    ]
    features = {k: getattr(track, k, None) for k in keys}
    if all(v is None for v in features.values()):
        return None
    return features


def _build_match_dict(m: MatchResult) -> dict:
    """Build a single match dict for JSON export."""
    t = m.track
    spotify_track = {
        "name": t.name,
        "artist": t.artist,
        "all_artists": t.all_artists,
        "album": t.album,
        "genres": t.genres,
        "release_date": t.release_date,
        "release_year": t.release_year,
        "popularity": t.popularity,
        "explicit": t.explicit,
        "track_number": t.track_number,
        "album_art_url": t.album_art_url,
        "duration_seconds": t.duration_seconds,
    }
    audio_features = _build_audio_features(t)
    if audio_features is not None:
        spotify_track["audio_features"] = audio_features

    return {
        "spotify_track": spotify_track,
        "youtube_url": m.youtube_result.url,
        "youtube_title": m.youtube_result.title,
        "audio_bitrate": m.audio_bitrate,
        "title_similarity": round(m.title_similarity, 3),
        "duration_match": m.duration_match,
    }


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
            _build_match_dict(m)
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
        "all_artists",
        "song",
        "album",
        "genres",
        "release_year",
        "popularity",
        "explicit",
        "track_number",
        "spotify_duration",
        "tempo",
        "energy",
        "danceability",
        "valence",
        "youtube_url",
        "youtube_title",
        "audio_bitrate",
        "title_similarity",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for m in matches:
            t = m.track
            writer.writerow({
                "artist": t.artist,
                "all_artists": "; ".join(t.all_artists) if t.all_artists else "",
                "song": t.name,
                "album": t.album,
                "genres": "; ".join(t.genres) if t.genres else "",
                "release_year": t.release_year or "",
                "popularity": t.popularity if t.popularity is not None else "",
                "explicit": t.explicit if t.explicit is not None else "",
                "track_number": t.track_number if t.track_number is not None else "",
                "spotify_duration": t.duration_seconds,
                "tempo": t.tempo if t.tempo is not None else "",
                "energy": t.energy if t.energy is not None else "",
                "danceability": t.danceability if t.danceability is not None else "",
                "valence": t.valence if t.valence is not None else "",
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
