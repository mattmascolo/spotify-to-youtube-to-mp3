"""Tests for export functionality."""

import json

import pytest
from pathlib import Path
from unittest.mock import Mock

from spotifytoyoutube.export import (
    Exporter,
    export_to_json,
    export_to_csv,
    export_to_m3u,
)
from spotifytoyoutube.matcher import MatchResult
from spotifytoyoutube.spotify_client import Track
from spotifytoyoutube.youtube_search import YouTubeResult


@pytest.fixture
def sample_matches() -> list[MatchResult]:
    """Create sample match results for testing."""
    matches = []
    for i in range(3):
        track = Track(
            id=f"sp{i}",
            name=f"Song {i}",
            artist=f"Artist {i}",
            album=f"Album {i}",
            duration_seconds=180 + i * 10,
        )

        yt_result = YouTubeResult(
            video_id=f"vid{i}",
            title=f"Artist {i} - Song {i}",
            duration_seconds=180 + i * 10,
            audio_bitrate=128 + i * 64,
            audio_codec="opus",
        )

        matches.append(
            MatchResult(
                track=track,
                youtube_result=yt_result,
                title_similarity=0.9 + i * 0.03,
                duration_match=True,
                audio_bitrate=128 + i * 64,
            )
        )
    return matches


class TestExportToJson:
    """Tests for JSON export."""

    def test_exports_valid_json(
        self, sample_matches: list[MatchResult], tmp_path: Path
    ) -> None:
        """export_to_json creates valid JSON file."""
        output_path = tmp_path / "output.json"
        export_to_json(sample_matches, output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert len(data["matches"]) == 3

    def test_json_includes_all_fields(
        self, sample_matches: list[MatchResult], tmp_path: Path
    ) -> None:
        """Exported JSON includes track and match metadata."""
        output_path = tmp_path / "output.json"
        export_to_json(sample_matches, output_path)

        data = json.loads(output_path.read_text())
        first_match = data["matches"][0]

        assert "spotify_track" in first_match
        assert "youtube_url" in first_match
        assert "audio_bitrate" in first_match
        assert "title_similarity" in first_match


class TestExportToCsv:
    """Tests for CSV export."""

    def test_exports_valid_csv(
        self, sample_matches: list[MatchResult], tmp_path: Path
    ) -> None:
        """export_to_csv creates valid CSV file."""
        output_path = tmp_path / "output.csv"
        export_to_csv(sample_matches, output_path)

        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 4  # header + 3 rows


class TestExportToM3u:
    """Tests for M3U playlist export."""

    def test_exports_valid_m3u(
        self, sample_matches: list[MatchResult], tmp_path: Path
    ) -> None:
        """export_to_m3u creates valid M3U playlist."""
        output_path = tmp_path / "output.m3u"
        export_to_m3u(sample_matches, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "#EXTM3U" in content
        assert "youtube.com" in content


class TestExporter:
    """Tests for Exporter class."""

    def test_auto_detects_format_from_extension(
        self, sample_matches: list[MatchResult], tmp_path: Path
    ) -> None:
        """Exporter auto-detects format from file extension."""
        exporter = Exporter()

        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        m3u_path = tmp_path / "out.m3u"

        exporter.export(sample_matches, json_path)
        exporter.export(sample_matches, csv_path)
        exporter.export(sample_matches, m3u_path)

        assert json_path.exists()
        assert csv_path.exists()
        assert m3u_path.exists()
