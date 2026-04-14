"""Track matching algorithm prioritizing audio quality."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Result of matching a Spotify track to an audio source."""

    track: Track
    youtube_result: YouTubeResult
    title_similarity: float
    duration_match: bool
    audio_bitrate: int
    isrc_verified: bool = False
    source: str = "youtube"

    @property
    def combined_score(self) -> float:
        """
        Calculate combined score prioritizing audio quality.

        The scoring formula weights:
        - Audio bitrate (normalized to 0-1, max 320kbps): 60%
        - Title similarity: 30%
        - Duration match bonus: 10%
        - ISRC verification bonus: +20% (when the YouTube video description
          contains the Spotify ISRC, we know it's the same recording)
        """
        bitrate_score = min(self.audio_bitrate / 320.0, 1.0)
        duration_bonus = 0.1 if self.duration_match else 0.0
        isrc_bonus = 0.2 if self.isrc_verified else 0.0

        return (
            bitrate_score * 0.6
            + self.title_similarity * 0.3
            + duration_bonus
            + isrc_bonus
        )


_DEFAULT_SOURCE_NAMES = ("youtube", "soundcloud")


class TrackMatcher:
    """Matches Spotify tracks to audio sources, prioritizing audio quality."""

    def __init__(
        self,
        searcher: YouTubeSearcher | None = None,
        duration_threshold: int = 10,
        min_title_similarity: float = 0.5,
        cache: MatchCache | None = None,
        rate_limiter: RateLimiter | None = None,
        skip_detailed_info: bool = False,
        *,
        searchers: list | None = None,
    ) -> None:
        """
        Initialize track matcher.

        Args:
            searcher: Single searcher (backwards-compatible positional form)
            duration_threshold: Max duration difference in seconds
            min_title_similarity: Minimum title similarity to consider
            cache: Optional MatchCache for caching results
            rate_limiter: Optional RateLimiter for API rate limiting
            skip_detailed_info: Skip fetching detailed info during scoring (faster)
            searchers: Ordered list of searchers; each source is tried in turn
                until one yields a usable match. Mutually exclusive with `searcher`.

        Raises:
            ValueError: If neither searcher nor searchers is provided.
        """
        if searchers is not None:
            if not searchers:
                raise ValueError("searchers list must not be empty")
            self.searchers = list(searchers)
        elif searcher is not None:
            self.searchers = [searcher]
        else:
            raise ValueError("TrackMatcher requires at least one searcher")

        # Backwards-compat alias for code that reads `self.searcher`.
        self.searcher = self.searchers[0]
        self.duration_threshold = duration_threshold
        self.min_title_similarity = min_title_similarity
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.skip_detailed_info = skip_detailed_info

    def find_best_match(
        self,
        track: Track,
        max_candidates: int = 10,
        on_progress: Callable[[str, dict], None] | None = None,
    ) -> MatchResult | None:
        """
        Find the best match for a Spotify track across all configured sources.

        Tries each searcher in order. The first source that produces a candidate
        passing the similarity/duration filters wins; subsequent sources are
        only consulted when the current source yields nothing usable.

        Returns:
            Best MatchResult, or None if no source produced a valid match.
        """
        def emit(event: str, **data: object) -> None:
            if on_progress:
                on_progress(event, {"track": track, **data})

        if self.cache:
            cached = self.cache.get(track.id)
            if cached:
                emit("cache_hit")
                yt_result = YouTubeResult(
                    video_id=cached["video_id"],
                    title=cached["title"],
                    duration_seconds=cached["duration_seconds"],
                    audio_bitrate=cached["audio_bitrate"],
                    audio_codec=cached.get("audio_codec", "unknown"),
                    override_url=cached.get("override_url"),
                )
                return MatchResult(
                    track=track,
                    youtube_result=yt_result,
                    title_similarity=cached["title_similarity"],
                    duration_match=cached["duration_match"],
                    audio_bitrate=cached["audio_bitrate"],
                    isrc_verified=cached.get("isrc_verified", False),
                    source=cached.get("source", "youtube"),
                )

        best: MatchResult | None = None
        for idx, searcher in enumerate(self.searchers):
            source_name = (
                _DEFAULT_SOURCE_NAMES[idx]
                if idx < len(_DEFAULT_SOURCE_NAMES)
                else f"source_{idx}"
            )
            best = self._search_one_source(
                track, searcher, source_name, max_candidates, emit
            )
            if best is not None:
                break

        if best is None:
            return None

        # ISRC verification (best-effort). Even in fast mode, pay the cost of
        # one extra get_video_info call for the winning candidate — correct
        # match identity is more valuable than one network request per track.
        if track.isrc:
            description = best.youtube_result.description
            if description is None:
                winning_searcher = self._searcher_for_source(best.source)
                if winning_searcher is not None:
                    detailed = winning_searcher.get_video_info(
                        best.youtube_result.video_id
                    )
                    if detailed and detailed.description is not None:
                        best.youtube_result.description = detailed.description
                        description = detailed.description
            if description and track.isrc.upper() in description.upper():
                best.isrc_verified = True
                emit("isrc_verified", isrc=track.isrc)

        emit(
            "best_match",
            title=best.youtube_result.title[:50],
            bitrate=best.audio_bitrate,
            similarity=best.title_similarity,
            source=best.source,
        )

        if self.cache:
            self.cache.set(track.id, {
                "video_id": best.youtube_result.video_id,
                "title": best.youtube_result.title,
                "duration_seconds": best.youtube_result.duration_seconds,
                "audio_bitrate": best.audio_bitrate,
                "audio_codec": best.youtube_result.audio_codec,
                "title_similarity": best.title_similarity,
                "duration_match": best.duration_match,
                "isrc_verified": best.isrc_verified,
                "source": best.source,
                "override_url": best.youtube_result.override_url,
            })

        return best

    def _searcher_for_source(self, source: str) -> object | None:
        for idx, searcher in enumerate(self.searchers):
            name = (
                _DEFAULT_SOURCE_NAMES[idx]
                if idx < len(_DEFAULT_SOURCE_NAMES)
                else f"source_{idx}"
            )
            if name == source:
                return searcher
        return None

    def _search_one_source(
        self,
        track: Track,
        searcher,
        source_name: str,
        max_candidates: int,
        emit: Callable[..., None],
    ) -> MatchResult | None:
        """Search a single source and return the best scoring candidate (or None)."""
        if self.rate_limiter:
            self.rate_limiter.wait()

        emit("searching", source=source_name)
        search_results = searcher.search(
            track.search_query,
            max_results=max_candidates,
        )

        if not search_results:
            emit("no_results", source=source_name)
            return None

        emit("found_candidates", source=source_name, count=len(search_results))
        candidates: list[MatchResult] = []

        for i, result in enumerate(search_results):
            emit("comparing", candidate_num=i + 1, candidate_title=result.title[:50])

            if self.skip_detailed_info:
                detailed = result
            else:
                if self.rate_limiter:
                    self.rate_limiter.wait()
                fetched = searcher.get_video_info(result.video_id)
                detailed = fetched if fetched else result

            title_similarity = MatchScore.calculate_title_similarity(
                track.search_query,
                detailed.title,
            )
            duration_match = MatchScore.duration_matches(
                track.duration_seconds,
                detailed.duration_seconds,
                self.duration_threshold,
            )

            if title_similarity < self.min_title_similarity:
                emit("skipped", reason="low_similarity", similarity=title_similarity)
                continue

            duration_diff = abs(track.duration_seconds - detailed.duration_seconds)
            if duration_diff > self.duration_threshold * 2:
                emit("skipped", reason="duration_mismatch", diff=duration_diff)
                continue

            emit(
                "candidate_accepted",
                title=detailed.title[:50],
                bitrate=detailed.audio_bitrate,
                similarity=title_similarity,
            )

            candidates.append(
                MatchResult(
                    track=track,
                    youtube_result=detailed,
                    title_similarity=title_similarity,
                    duration_match=duration_match,
                    audio_bitrate=detailed.audio_bitrate,
                    source=source_name,
                )
            )

        if not candidates:
            emit("no_valid_candidates", source=source_name)
            return None

        return max(candidates, key=lambda m: m.combined_score)

    def find_matches(
        self,
        tracks: list[Track],
        max_candidates: int = 10,
    ) -> list[MatchResult]:
        """
        Find best YouTube matches for multiple tracks (sequential).

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

    def find_matches_parallel(
        self,
        tracks: list[Track],
        max_candidates: int = 10,
        max_workers: int = 8,
        on_complete: Callable[[Track, MatchResult | None], None] | None = None,
        on_progress: Callable[[str, dict], None] | None = None,
    ) -> list[MatchResult]:
        """
        Find best YouTube matches for multiple tracks in parallel.

        Args:
            tracks: List of Spotify tracks
            max_candidates: Max search results per track
            max_workers: Maximum concurrent searches
            on_complete: Callback called for each completed match (track, result)
            on_progress: Callback for detailed progress updates (event_type, data)

        Returns:
            List of MatchResult for successful matches (order preserved)
        """
        results: dict[str, MatchResult | None] = {}

        def process_track(track: Track) -> tuple[Track, MatchResult | None]:
            result = self.find_best_match(track, max_candidates, on_progress=on_progress)
            return track, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_track, track): track for track in tracks}

            for future in as_completed(futures):
                track, result = future.result()
                results[track.id] = result
                if on_complete:
                    on_complete(track, result)

        # Return in original order
        return [results[t.id] for t in tracks if results.get(t.id) is not None]
