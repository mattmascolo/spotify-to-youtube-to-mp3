"""Command-line interface for SpotifyToYouTube."""

import os
import sys

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from spotifytoyoutube.matcher import MatchResult, TrackMatcher
from spotifytoyoutube.spotify_auth import SpotifyAuthenticator
from spotifytoyoutube.spotify_client import SpotifyClient, Track
from spotifytoyoutube.youtube_search import YouTubeSearcher

console = Console()


def get_spotify_credentials() -> tuple[str, str]:
    """
    Get Spotify credentials from environment.

    Returns:
        Tuple of (client_id, client_secret)

    Raises:
        click.ClickException: If credentials not found
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise click.ClickException(
            "Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET environment variables."
        )

    return client_id, client_secret


@click.group()
@click.version_option()
def main() -> None:
    """Fetch Spotify liked songs and find highest quality YouTube matches."""
    pass


@main.command()
def auth() -> None:
    """Authenticate with Spotify and verify credentials."""
    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(f"[red]Error:[/red] {e.message}")
        sys.exit(1)

    console.print("Authenticating with Spotify...")

    try:
        authenticator = SpotifyAuthenticator(
            client_id=client_id,
            client_secret=client_secret,
        )
        sp = authenticator.get_client()
        user = sp.current_user()

        console.print(f"[green]Success![/green] Authenticated as: {user['display_name']}")
    except Exception as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        sys.exit(1)


@main.command()
@click.option(
    "--limit", "-l",
    default=50,
    help="Maximum number of tracks to fetch",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file path (default: stdout)",
)
def fetch(limit: int, output: str | None) -> None:
    """Fetch liked songs from Spotify."""
    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(f"[red]Error:[/red] {e.message}")
        sys.exit(1)

    authenticator = SpotifyAuthenticator(
        client_id=client_id,
        client_secret=client_secret,
    )
    sp = authenticator.get_client()
    client = SpotifyClient(sp)

    tracks: list[Track] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching liked songs...", total=None)

        for track in client.get_liked_songs(max_tracks=limit):
            tracks.append(track)
            progress.update(task, description=f"Fetched {len(tracks)} tracks...")

    # Create output table
    table = Table(title=f"Liked Songs ({len(tracks)} tracks)")
    table.add_column("Artist", style="cyan")
    table.add_column("Song", style="green")
    table.add_column("Album", style="dim")

    for track in tracks:
        table.add_row(track.artist, track.name, track.album)

    if output:
        # Write to file as simple list
        with open(output, "w") as f:
            for track in tracks:
                f.write(f"{track.search_query}\n")
        console.print(f"[green]Saved {len(tracks)} tracks to {output}[/green]")
    else:
        console.print(table)


@main.command()
@click.option(
    "--limit", "-l",
    default=10,
    help="Maximum number of tracks to match",
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file for YouTube URLs",
)
@click.option(
    "--duration-threshold", "-d",
    default=10,
    help="Max duration difference in seconds",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed match information",
)
def match(
    limit: int,
    output: str | None,
    duration_threshold: int,
    verbose: bool,
) -> None:
    """Find YouTube matches for liked songs."""
    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(f"[red]Error:[/red] {e.message}")
        sys.exit(1)

    # Setup clients
    authenticator = SpotifyAuthenticator(
        client_id=client_id,
        client_secret=client_secret,
    )
    sp = authenticator.get_client()
    spotify_client = SpotifyClient(sp)
    youtube_searcher = YouTubeSearcher(quiet=True)
    matcher = TrackMatcher(
        youtube_searcher,
        duration_threshold=duration_threshold,
    )

    # Fetch tracks
    tracks: list[Track] = []
    console.print("Fetching liked songs from Spotify...")

    for track in spotify_client.get_liked_songs(max_tracks=limit):
        tracks.append(track)

    console.print(f"Found {len(tracks)} tracks. Finding YouTube matches...")

    # Match tracks
    matches: list[MatchResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Matching...", total=len(tracks))

        for track in tracks:
            progress.update(
                task,
                description=f"Matching: {track.artist} - {track.name}",
            )
            result = matcher.find_best_match(track)
            if result:
                matches.append(result)
            progress.advance(task)

    # Output results
    console.print(f"\n[green]Found {len(matches)}/{len(tracks)} matches[/green]\n")

    if verbose:
        table = Table(title="YouTube Matches")
        table.add_column("Spotify Track", style="cyan")
        table.add_column("YouTube Match", style="green")
        table.add_column("Bitrate", style="yellow")
        table.add_column("Similarity", style="dim")

        for m in matches:
            table.add_row(
                m.track.search_query,
                m.youtube_result.title[:50],
                f"{m.audio_bitrate}kbps",
                f"{m.title_similarity:.0%}",
            )

        console.print(table)
    else:
        for m in matches:
            console.print(m.youtube_result.url)

    if output:
        with open(output, "w") as f:
            for m in matches:
                f.write(f"{m.youtube_result.url}\n")
        console.print(f"\n[green]Saved {len(matches)} URLs to {output}[/green]")


if __name__ == "__main__":
    main()
