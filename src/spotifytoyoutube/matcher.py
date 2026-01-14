"""Track matching algorithm prioritizing audio quality."""

from dataclasses import dataclass
from difflib import SequenceMatcher

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
    ) -> None:
        """
        Initialize track matcher.

        Args:
            searcher: YouTubeSearcher instance
            duration_threshold: Max duration difference in seconds
            min_title_similarity: Minimum title similarity to consider
        """
        self.searcher = searcher
        self.duration_threshold = duration_threshold
        self.min_title_similarity = min_title_similarity

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
        # Search YouTube
        search_results = self.searcher.search(
            track.search_query,
            max_results=max_candidates,
        )

        if not search_results:
            return None

        candidates: list[MatchResult] = []

        for result in search_results:
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

        # Return best match by combined score
        return max(candidates, key=lambda m: m.combined_score)

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
