"""Track matching algorithm prioritizing audio quality."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from spotifytoyoutube.cache import MatchCache, RateLimiter
from spotifytoyoutube.spotify_client import Track
from spotifytoyoutube.youtube_search import YouTubeResult, YouTubeSearcher


class MatchScore:
    """Utility class for calculating match scores."""

    @staticmethod
    def calculate_title_similarity(title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles.

        Args:
            title1: First title string
            title2: Second title string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        return SequenceMatcher(None, t1, t2).ratio()

    @staticmethod
    def duration_matches(
        spotify_duration: int,
        youtube_duration: int,
        threshold: int = 10,
    ) -> bool:
        """
        Check if durations match within threshold.

        Args:
            spotify_duration: Spotify track duration in seconds
            youtube_duration: YouTube video duration in seconds
            threshold: Maximum allowed difference in seconds

        Returns:
            True if durations are within threshold
        """
        return abs(spotify_duration - youtube_duration) <= threshold


@dataclass
class MatchResult:
    """Result of matching a Spotify track to a YouTube video."""

    track: Track
    youtube_result: YouTubeResult
    title_similarity: float
    duration_match: bool
    audio_bitrate: int

    @property
    def combined_score(self) -> float:
        """
        Calculate combined score prioritizing audio quality.

        The scoring formula weights:
        - Audio bitrate (normalized to 0-1, max 320kbps): 60%
        - Title similarity: 30%
        - Duration match bonus: 10%

        Returns:
            Combined score between 0.0 and 1.0
        """
        # Normalize bitrate to 0-1 scale (assuming max 320kbps)
        bitrate_score = min(self.audio_bitrate / 320.0, 1.0)

        duration_bonus = 0.1 if self.duration_match else 0.0

        return (
            bitrate_score * 0.6
            + self.title_similarity * 0.3
            + duration_bonus
        )


class TrackMatcher:
    """Matches Spotify tracks to YouTube videos prioritizing audio quality."""

    def __init__(
        self,
        searcher: YouTubeSearcher,
        duration_threshold: int = 10,
        min_title_similarity: float = 0.5,
        cache: MatchCache | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """
        Initialize track matcher.

        Args:
            searcher: YouTubeSearcher instance
            duration_threshold: Max duration difference in seconds
            min_title_similarity: Minimum title similarity to consider
            cache: Optional MatchCache for caching results
            rate_limiter: Optional RateLimiter for API rate limiting
        """
        self.searcher = searcher
        self.duration_threshold = duration_threshold
        self.min_title_similarity = min_title_similarity
        self.cache = cache
        self.rate_limiter = rate_limiter

    def find_best_match(
        self,
        track: Track,
        max_candidates: int = 10,
    ) -> MatchResult | None:
        """
        Find the best YouTube match for a Spotify track.

        Prioritizes audio quality, then exact match accuracy.

        Args:
            track: Spotify track to match
            max_candidates: Maximum search results to evaluate

        Returns:
            Best MatchResult, or None if no suitable match found
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(track.id)
            if cached:
                yt_result = YouTubeResult(
                    video_id=cached["video_id"],
                    title=cached["title"],
                    duration_seconds=cached["duration_seconds"],
                    audio_bitrate=cached["audio_bitrate"],
                    audio_codec=cached.get("audio_codec", "unknown"),
                )
                return MatchResult(
                    track=track,
                    youtube_result=yt_result,
                    title_similarity=cached["title_similarity"],
                    duration_match=cached["duration_match"],
                    audio_bitrate=cached["audio_bitrate"],
                )

        # Rate limit if configured
        if self.rate_limiter:
            self.rate_limiter.wait()

        # Search YouTube
        search_results = self.searcher.search(
            track.search_query,
            max_results=max_candidates,
        )

        if not search_results:
            return None

        candidates: list[MatchResult] = []

        for result in search_results:
            if self.rate_limiter:
                self.rate_limiter.wait()

            # Get detailed video info for accurate bitrate
            detailed = self.searcher.get_video_info(result.video_id)
            if not detailed:
                detailed = result

            # Calculate match scores
            title_similarity = MatchScore.calculate_title_similarity(
                track.search_query,
                detailed.title,
            )

            duration_match = MatchScore.duration_matches(
                track.duration_seconds,
                detailed.duration_seconds,
                self.duration_threshold,
            )

            # Skip if title similarity too low
            if title_similarity < self.min_title_similarity:
                continue

            # Skip if duration is way off (more than 2x threshold)
            duration_diff = abs(track.duration_seconds - detailed.duration_seconds)
            if duration_diff > self.duration_threshold * 2:
                continue

            candidates.append(
                MatchResult(
                    track=track,
                    youtube_result=detailed,
                    title_similarity=title_similarity,
                    duration_match=duration_match,
                    audio_bitrate=detailed.audio_bitrate,
                )
            )

        if not candidates:
            return None

        # Get best match
        best = max(candidates, key=lambda m: m.combined_score)

        # Cache result
        if self.cache:
            self.cache.set(track.id, {
                "video_id": best.youtube_result.video_id,
                "title": best.youtube_result.title,
                "duration_seconds": best.youtube_result.duration_seconds,
                "audio_bitrate": best.audio_bitrate,
                "audio_codec": best.youtube_result.audio_codec,
                "title_similarity": best.title_similarity,
                "duration_match": best.duration_match,
            })

        return best

    def find_matches(
        self,
        tracks: list[Track],
        max_candidates: int = 10,
    ) -> list[MatchResult]:
        """
        Find best YouTube matches for multiple tracks.

        Args:
            tracks: List of Spotify tracks
            max_candidates: Max search results per track

        Returns:
            List of MatchResult for successful matches
        """
        results = []
        for track in tracks:
            match = self.find_best_match(track, max_candidates)
            if match:
                results.append(match)
        return results
