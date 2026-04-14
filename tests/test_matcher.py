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


class TestIsrcVerification:
    """Tests for ISRC-based match verification."""

    def _make_yt(self, description: str | None = None) -> YouTubeResult:
        return YouTubeResult(
            video_id="v1",
            title="Artist - Song",
            duration_seconds=180,
            audio_bitrate=256,
            audio_codec="opus",
            description=description,
        )

    def _make_track(self, isrc: str | None = "USUM71703861") -> Track:
        return Track(
            id="sp1",
            name="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
            isrc=isrc,
        )

    def test_isrc_verified_when_description_contains_code(self) -> None:
        mock_searcher = Mock()
        mock_searcher.search.return_value = [self._make_yt()]
        mock_searcher.get_video_info.return_value = self._make_yt(
            description="Provided to YouTube by UMG\nISRC: USUM71703861",
        )

        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(self._make_track())

        assert match is not None
        assert match.isrc_verified is True

    def test_isrc_case_insensitive_match(self) -> None:
        mock_searcher = Mock()
        mock_searcher.search.return_value = [self._make_yt()]
        mock_searcher.get_video_info.return_value = self._make_yt(
            description="isrc: usum71703861 somewhere",
        )
        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(self._make_track())
        assert match is not None
        assert match.isrc_verified is True

    def test_isrc_not_verified_when_description_missing(self) -> None:
        mock_searcher = Mock()
        mock_searcher.search.return_value = [self._make_yt()]
        mock_searcher.get_video_info.return_value = self._make_yt(
            description="Random fan upload",
        )
        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(self._make_track())
        assert match is not None
        assert match.isrc_verified is False

    def test_no_isrc_on_track_skips_verification(self) -> None:
        mock_searcher = Mock()
        mock_searcher.search.return_value = [self._make_yt()]
        mock_searcher.get_video_info.return_value = self._make_yt()
        matcher = TrackMatcher(mock_searcher)
        match = matcher.find_best_match(self._make_track(isrc=None))
        assert match is not None
        assert match.isrc_verified is False

    def test_isrc_boost_applies_to_combined_score(self) -> None:
        verified = MatchResult(
            track=Mock(),
            youtube_result=Mock(),
            title_similarity=0.8,
            duration_match=True,
            audio_bitrate=256,
            isrc_verified=True,
        )
        unverified = MatchResult(
            track=Mock(),
            youtube_result=Mock(),
            title_similarity=0.8,
            duration_match=True,
            audio_bitrate=256,
            isrc_verified=False,
        )
        assert verified.combined_score > unverified.combined_score

    def test_isrc_verification_in_fast_mode_fetches_description(self) -> None:
        """Even in fast mode, verification fetches description for the top candidate."""
        mock_searcher = Mock()
        mock_searcher.search.return_value = [self._make_yt()]
        mock_searcher.get_video_info.return_value = self._make_yt(
            description="ISRC: USUM71703861",
        )

        matcher = TrackMatcher(mock_searcher, skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())
        assert match is not None
        assert match.isrc_verified is True
        mock_searcher.get_video_info.assert_called()


class TestMultiSourceFallback:
    """Tests for the multi-searcher fallback behavior."""

    def _make_track(self) -> Track:
        return Track(
            id="sp1",
            name="Song",
            artist="Artist",
            album="Album",
            duration_seconds=180,
        )

    def _yt(
        self,
        vid: str = "v1",
        title: str = "Artist - Song",
        override_url: str | None = None,
    ) -> YouTubeResult:
        return YouTubeResult(
            video_id=vid,
            title=title,
            duration_seconds=180,
            audio_bitrate=256,
            audio_codec="opus",
            override_url=override_url,
        )

    def test_youtube_used_when_it_yields_match(self) -> None:
        yt = Mock()
        yt.search.return_value = [self._yt()]
        yt.get_video_info.return_value = None
        sc = Mock()

        matcher = TrackMatcher(searchers=[yt, sc], skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())

        assert match is not None
        assert match.source == "youtube"
        sc.search.assert_not_called()

    def test_falls_back_to_soundcloud_when_youtube_has_no_match(self) -> None:
        yt = Mock()
        yt.search.return_value = []
        yt.get_video_info.return_value = None
        sc = Mock()
        sc.search.return_value = [
            self._yt(
                vid="sc1",
                override_url="https://soundcloud.com/artist/song",
            ),
        ]
        sc.get_video_info.return_value = None

        matcher = TrackMatcher(searchers=[yt, sc], skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())

        assert match is not None
        assert match.source == "soundcloud"
        assert match.youtube_result.url == "https://soundcloud.com/artist/song"

    def test_falls_back_when_youtube_below_similarity(self) -> None:
        yt = Mock()
        yt.search.return_value = [
            self._yt(title="TOTALLY UNRELATED GARBAGE"),
        ]
        yt.get_video_info.return_value = None
        sc = Mock()
        sc.search.return_value = [
            self._yt(
                vid="sc1",
                override_url="https://soundcloud.com/artist/song",
            ),
        ]
        sc.get_video_info.return_value = None

        matcher = TrackMatcher(searchers=[yt, sc], skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())

        assert match is not None
        assert match.source == "soundcloud"

    def test_returns_none_when_all_sources_fail(self) -> None:
        yt = Mock()
        yt.search.return_value = []
        yt.get_video_info.return_value = None
        sc = Mock()
        sc.search.return_value = []
        sc.get_video_info.return_value = None

        matcher = TrackMatcher(searchers=[yt, sc], skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())
        assert match is None

    def test_single_searcher_positional_still_works(self) -> None:
        """Backwards compat: positional searcher= still creates a single-source matcher."""
        yt = Mock()
        yt.search.return_value = [self._yt()]
        yt.get_video_info.return_value = None

        matcher = TrackMatcher(yt, skip_detailed_info=True)
        match = matcher.find_best_match(self._make_track())
        assert match is not None
        assert match.source == "youtube"

    def test_raises_when_no_searcher_provided(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            TrackMatcher()
