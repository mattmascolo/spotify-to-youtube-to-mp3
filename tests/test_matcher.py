"""Tests for track matching algorithm."""

from unittest.mock import Mock

from spotifytoyoutube.matcher import MatchResult, MatchScore, TrackMatcher
from spotifytoyoutube.spotify_client import Track
from spotifytoyoutube.youtube_search import YouTubeResult


class TestMatchScore:
    """Tests for MatchScore calculation."""

    def test_title_similarity_exact_match(self) -> None:
        """Exact title match returns 1.0 similarity."""
        score = MatchScore.calculate_title_similarity(
            "Artist - Song Title",
            "Artist - Song Title"
        )
        assert score == 1.0

    def test_title_similarity_case_insensitive(self) -> None:
        """Title matching is case insensitive."""
        score = MatchScore.calculate_title_similarity(
            "Artist - Song Title",
            "ARTIST - SONG TITLE"
        )
        assert score == 1.0

    def test_title_similarity_partial_match(self) -> None:
        """Partial matches return proportional similarity."""
        score = MatchScore.calculate_title_similarity(
            "Artist - Song",
            "Artist - Song (Official Video)"
        )
        assert 0.5 < score < 1.0

    def test_duration_match_within_threshold(self) -> None:
        """Duration within threshold returns True."""
        assert MatchScore.duration_matches(180, 182, threshold=5) is True
        assert MatchScore.duration_matches(180, 175, threshold=5) is True

    def test_duration_match_outside_threshold(self) -> None:
        """Duration outside threshold returns False."""
        assert MatchScore.duration_matches(180, 190, threshold=5) is False


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_match_result_creation(self) -> None:
        """MatchResult stores track, YouTube result, and scores."""
        track = Track(
            id="sp123",
            name="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_seconds=180,
        )
        yt_result = YouTubeResult(
            video_id="yt123",
            title="Test Artist - Test Song",
            duration_seconds=180,
            audio_bitrate=160,
            audio_codec="opus",
        )
        match = MatchResult(
            track=track,
            youtube_result=yt_result,
            title_similarity=0.95,
            duration_match=True,
            audio_bitrate=160,
        )

        assert match.track == track
        assert match.youtube_result == yt_result
        assert match.title_similarity == 0.95

    def test_combined_score_quality_first(self) -> None:
        """Combined score prioritizes audio bitrate."""
        high_quality = MatchResult(
            track=Mock(),
            youtube_result=Mock(),
            title_similarity=0.8,
            duration_match=True,
            audio_bitrate=320,
        )
        low_quality = MatchResult(
            track=Mock(),
            youtube_result=Mock(),
            title_similarity=0.95,
            duration_match=True,
            audio_bitrate=128,
        )

        # Higher bitrate should have higher combined score
        assert high_quality.combined_score > low_quality.combined_score


class TestTrackMatcher:
    """Tests for TrackMatcher class."""

    def test_find_best_match_returns_highest_combined_score(self) -> None:
        """find_best_match returns result with highest combined score."""
        mock_searcher = Mock()
        mock_searcher.search.return_value = [
            YouTubeResult(
                video_id="low_quality",
                title="Artist - Song",
                duration_seconds=180,
                audio_bitrate=128,
                audio_codec="mp3",
            ),
            YouTubeResult(
                video_id="high_quality",
                title="Artist - Song",
                duration_seconds=180,
                audio_bitrate=320,
                audio_codec="opus",
            ),
        ]
        mock_searcher.get_video_info.side_effect = lambda vid: YouTubeResult(
            video_id=vid,
            title="Artist - Song",
            duration_seconds=180,
            audio_bitrate=320 if vid == "high_quality" else 128,
            audio_codec="opus" if vid == "high_quality" else "mp3",
        )

        track = Track(
            id="sp123",
            name="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
        )

        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(track)

        assert match is not None
        assert match.youtube_result.video_id == "high_quality"

    def test_find_best_match_filters_duration_mismatch(self) -> None:
        """find_best_match filters out results with wrong duration."""
        mock_searcher = Mock()
        mock_searcher.search.return_value = [
            YouTubeResult(
                video_id="wrong_duration",
                title="Artist - Song",
                duration_seconds=600,  # 10 minutes, way off
                audio_bitrate=320,
                audio_codec="opus",
            ),
            YouTubeResult(
                video_id="correct_duration",
                title="Artist - Song",
                duration_seconds=182,
                audio_bitrate=128,
                audio_codec="mp3",
            ),
        ]
        mock_searcher.get_video_info.side_effect = lambda vid: YouTubeResult(
            video_id=vid,
            title="Artist - Song",
            duration_seconds=600 if vid == "wrong_duration" else 182,
            audio_bitrate=320 if vid == "wrong_duration" else 128,
            audio_codec="opus" if vid == "wrong_duration" else "mp3",
        )

        track = Track(
            id="sp123",
            name="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
        )

        matcher = TrackMatcher(mock_searcher, duration_threshold=10)
        match = matcher.find_best_match(track)

        assert match is not None
        assert match.youtube_result.video_id == "correct_duration"

    def test_find_best_match_returns_none_when_no_matches(self) -> None:
        """find_best_match returns None when no suitable matches found."""
        mock_searcher = Mock()
        mock_searcher.search.return_value = []

        track = Track(
            id="sp123",
            name="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
        )

        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(track)

        assert match is None
