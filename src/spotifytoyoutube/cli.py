"""Command-line interface for SpotifyToYouTube."""

import os
import sys
import threading
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from spotifytoyoutube.cache import MatchCache
from spotifytoyoutube.export import Exporter
from spotifytoyoutube.matcher import MatchResult, TrackMatcher
from spotifytoyoutube.spotify_auth import SpotifyAuthenticator
from spotifytoyoutube.spotify_client import SpotifyClient, Track
from spotifytoyoutube.youtube_search import YouTubeSearcher

console = Console()

BANNER = r"""
[bold cyan]
                    ╭──────────────────────────────────────────╮
                    │  [bold green]♫[/bold green] [bold white]Spotify[/bold white] [bold red]→[/bold red] [bold yellow]YouTube[/bold yellow] [bold green]♫[/bold green]                   │
                    │     [dim]High Quality Music Matcher[/dim]           │
                    ╰──────────────────────────────────────────╯
[/bold cyan]
[bold yellow]            ,---------------------------,
            |  /---------------------\  |
            | |                       | |
            | |   [bold green]  ♪ ♫ ♪ ♫ ♪ ♫ ♪    [/bold green]| |
            | |   [bold cyan]  Loading your     [/bold cyan]| |
            | |   [bold cyan]  favorite tunes   [/bold cyan]| |
            | |   [bold green]  ♫ ♪ ♫ ♪ ♫ ♪ ♫    [/bold green]| |
            | |                       | |
            |  \_____________________/  |
            |___________________________|
          ,---\_____     []     _______/------,
        /         /______________\           /|
      /___________________________________ /  | ___
      |                                   |   |    )
      |  _ _ _                 [__]  |   |    )
      |  o o o                 [___] |   |   /
      |_________________________________ |  /
  /-------------------------------------/|/
/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/ /
/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/ /
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/bold yellow]
[bold magenta]
         [dim]meow[/dim]   /
            ╱|、
          (˚ˎ 。7
           |、˜〵
           じしˍ,)ノ
[/bold magenta]
[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]
[bold white]         🎵 Find the HIGHEST QUALITY YouTube matches for your Spotify 🎵[/bold white]
[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]
"""

MINI_BANNER = """[bold green]♫[/bold green] [bold white]Spotify[/bold white][bold red]→[/bold red][bold yellow]YouTube[/bold yellow] [bold green]♫[/bold green]"""


def get_spotify_credentials() -> tuple[str, str]:
    """Get Spotify credentials from environment."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise click.ClickException(
            "Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET environment variables."
        )

    return client_id, client_secret


def show_banner(mini: bool = False) -> None:
    """Display the application banner."""
    if mini:
        console.print(MINI_BANNER, justify="center")
    else:
        console.print(BANNER)


@click.group()
@click.version_option()
def main() -> None:
    """Fetch Spotify liked songs and find highest quality YouTube matches."""
    pass


@main.command()
def auth() -> None:
    """Authenticate with Spotify and verify credentials."""
    show_banner(mini=True)
    console.print()

    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(Panel(f"[red]✗[/red] {e.message}", title="Error", border_style="red"))
        sys.exit(1)

    with console.status("[bold cyan]🔐 Connecting to Spotify...[/bold cyan]", spinner="dots"):
        try:
            authenticator = SpotifyAuthenticator(
                client_id=client_id,
                client_secret=client_secret,
            )
            sp = authenticator.get_client()
            user = sp.current_user()
        except Exception as e:
            console.print(Panel(f"[red]✗[/red] {e}", title="Auth Failed", border_style="red"))
            sys.exit(1)

    console.print(
        Panel(
            f"[green]✓[/green] Authenticated as [bold cyan]{user['display_name']}[/bold cyan]",
            title="Success",
            border_style="green",
        )
    )


@main.command()
@click.option("--limit", "-l", default=50, help="Maximum number of tracks to fetch")
@click.option("--output", "-o", type=click.Path(), help="Output file path (default: stdout)")
def fetch(limit: int, output: str | None) -> None:
    """Fetch liked songs from Spotify."""
    show_banner(mini=True)
    console.print()

    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(Panel(f"[red]✗[/red] {e.message}", title="Error", border_style="red"))
        sys.exit(1)

    authenticator = SpotifyAuthenticator(client_id=client_id, client_secret=client_secret)
    sp = authenticator.get_client()
    client = SpotifyClient(sp)

    tracks: list[Track] = []

    with Progress(
        SpinnerColumn(style="green"),
        TextColumn("[bold blue]{task.description}[/bold blue]"),
        BarColumn(bar_width=40, style="green", complete_style="bold green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("🎵 Fetching liked songs...", total=limit)

        for track in client.get_liked_songs(max_tracks=limit):
            tracks.append(track)
            progress.update(task, completed=len(tracks))
            progress.update(
                task, description=f"🎵 Found: [cyan]{track.artist}[/cyan] - {track.name}"
            )

    console.print()

    # Create output table
    table = Table(
        title=f"[bold]💿 Your Liked Songs ({len(tracks)} tracks)[/bold]",
        border_style="cyan",
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Artist", style="cyan")
    table.add_column("Song", style="green")
    table.add_column("Album", style="dim")

    for i, track in enumerate(tracks, 1):
        table.add_row(str(i), track.artist, track.name, track.album)

    if output:
        with open(output, "w") as f:
            for track in tracks:
                f.write(f"{track.search_query}\n")
        console.print(
            Panel(
                f"[green]✓[/green] Saved [bold]{len(tracks)}[/bold] tracks to [cyan]{output}[/cyan]",
                border_style="green",
            )
        )
    else:
        console.print(table)


@main.command()
@click.option("--limit", "-l", default=10, help="Maximum number of tracks to match")
@click.option("--output", "-o", type=click.Path(), help="Output file for YouTube URLs")
@click.option("--duration-threshold", "-d", default=10, help="Max duration difference in seconds")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed match information")
@click.option("--fast", "-f", is_flag=True, help="Fast mode: parallel searches, skip detailed info")
@click.option("--workers", "-w", default=8, help="Number of parallel workers (with --fast)")
@click.option("--no-cache", is_flag=True, help="Disable result caching")
def match(
    limit: int,
    output: str | None,
    duration_threshold: int,
    verbose: bool,
    fast: bool,
    workers: int,
    no_cache: bool,
) -> None:
    """Find YouTube matches for liked songs."""
    show_banner()

    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException as e:
        console.print(Panel(f"[red]✗[/red] {e.message}", title="Error", border_style="red"))
        sys.exit(1)

    # Setup cache
    cache = None if no_cache else MatchCache()

    # Setup clients
    authenticator = SpotifyAuthenticator(client_id=client_id, client_secret=client_secret)
    sp = authenticator.get_client()
    spotify_client = SpotifyClient(sp)
    youtube_searcher = YouTubeSearcher(quiet=True)
    matcher = TrackMatcher(
        youtube_searcher,
        duration_threshold=duration_threshold,
        cache=cache,
        skip_detailed_info=fast,
    )

    # Fetch tracks
    tracks: list[Track] = []

    mode_info = "[bold magenta]⚡ FAST MODE[/bold magenta] " if fast else ""
    console.print(
        Panel(
            f"{mode_info}[bold cyan]📡 PHASE 1:[/bold cyan] Connecting to Spotify API...",
            border_style="cyan",
        )
    )

    with console.status("[bold green]🎵 Loading your liked songs...[/bold green]", spinner="dots"):
        for track in spotify_client.get_liked_songs(max_tracks=limit):
            tracks.append(track)

    console.print(f"    [green]✓[/green] Loaded [bold]{len(tracks)}[/bold] tracks from Spotify\n")

    # Match tracks
    parallel_info = f" [dim]({workers} parallel workers)[/dim]" if fast else ""
    console.print(
        Panel(
            f"[bold yellow]🔍 PHASE 2:[/bold yellow] Searching YouTube for best quality matches...{parallel_info}",
            border_style="yellow",
        )
    )

    matches: list[MatchResult] = []
    failed: list[Track] = []
    completed_count = 0

    if fast:
        # Parallel mode with detailed progress
        print_lock = threading.Lock()

        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=40, style="yellow", complete_style="bold yellow"),
            TaskProgressColumn(),
            TextColumn("[dim]•[/dim]"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"[magenta]⚡ Parallel search ({workers} workers)...", total=len(tracks))

            def on_progress(event: str, data: dict) -> None:
                """Handle progress events from parallel searches."""
                if not verbose:
                    return
                track = data.get("track")
                track_name = f"[cyan]{track.artist}[/cyan] - {track.name[:25]}" if track else "Unknown"

                with print_lock:
                    if event == "cache_hit":
                        console.print(f"      [dim]💾 Cache hit:[/dim] {track_name}")
                    elif event == "searching":
                        console.print(f"      [dim]🔍 Searching:[/dim] {track_name}")
                    elif event == "found_candidates":
                        count = data.get("count", 0)
                        console.print(f"      [dim]   └─ Found {count} candidates[/dim]")
                    elif event == "comparing":
                        num = data.get("candidate_num", "?")
                        title = data.get("candidate_title", "")[:35]
                        console.print(f"      [dim]   └─ Comparing #{num}: {title}[/dim]")
                    elif event == "candidate_accepted":
                        bitrate = data.get("bitrate", 0)
                        similarity = data.get("similarity", 0)
                        console.print(f"      [dim]      ✓ Accepted ({bitrate:.0f}kbps, {similarity:.0%} match)[/dim]")
                    elif event == "skipped":
                        reason = data.get("reason", "unknown")
                        if reason == "low_similarity":
                            sim = data.get("similarity", 0)
                            console.print(f"      [dim]      ✗ Skipped (similarity {sim:.0%} too low)[/dim]")
                        elif reason == "duration_mismatch":
                            diff = data.get("diff", 0)
                            console.print(f"      [dim]      ✗ Skipped (duration off by {diff}s)[/dim]")
                    elif event == "best_match":
                        title = data.get("title", "")[:35]
                        bitrate = data.get("bitrate", 0)
                        console.print(f"      [green]   ★ Best: {title} ({bitrate:.0f}kbps)[/green]")

            def on_complete(track: Track, result: MatchResult | None) -> None:
                nonlocal completed_count
                with print_lock:
                    completed_count += 1
                    progress.update(task, completed=completed_count)
                    if result:
                        matches.append(result)
                        if verbose:
                            console.print(
                                f"    [green]✓[/green] [dim]#{completed_count}[/dim] "
                                f"[cyan]{track.artist}[/cyan] - {track.name} "
                                f"[dim]→[/dim] [yellow]{result.audio_bitrate:.0f}kbps[/yellow]"
                            )
                    else:
                        failed.append(track)
                        if verbose:
                            console.print(
                                f"    [red]✗[/red] [dim]#{completed_count}[/dim] "
                                f"[cyan]{track.artist}[/cyan] - {track.name} [red](no match)[/red]"
                            )

            matcher.find_matches_parallel(
                tracks,
                max_workers=workers,
                on_complete=on_complete,
                on_progress=on_progress if verbose else None,
            )
    else:
        # Sequential mode
        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=40, style="yellow", complete_style="bold yellow"),
            TaskProgressColumn(),
            TextColumn("[dim]•[/dim]"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing...", total=len(tracks))

            for i, track in enumerate(tracks, 1):
                progress.update(
                    task,
                    description=f"[cyan]{track.artist}[/cyan] - {track.name[:30]}",
                )

                result = matcher.find_best_match(track)

                if result:
                    matches.append(result)
                    if verbose:
                        console.print(
                            f"    [green]✓[/green] [dim]#{i}[/dim] "
                            f"[cyan]{track.artist}[/cyan] - {track.name}\n"
                            f"      [dim]└─►[/dim] [yellow]{result.youtube_result.title[:50]}[/yellow]\n"
                            f"          [dim]Quality:[/dim] [bold green]{result.audio_bitrate:.0f}kbps[/bold green] "
                            f"[dim]│[/dim] [dim]Match:[/dim] [bold]{result.title_similarity:.0%}[/bold] "
                            f"[dim]│[/dim] [dim]URL:[/dim] [blue]{result.youtube_result.url}[/blue]"
                        )
                else:
                    failed.append(track)
                    if verbose:
                        console.print(
                            f"    [red]✗[/red] [dim]#{i}[/dim] "
                            f"[cyan]{track.artist}[/cyan] - {track.name} [red](no match)[/red]"
                        )

                progress.advance(task)

    # Summary
    console.print()
    success_rate = len(matches) / len(tracks) * 100 if tracks else 0

    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style="bold")
    summary_table.add_column()

    summary_table.add_row("📊 Total Tracks:", f"[bold]{len(tracks)}[/bold]")
    summary_table.add_row("✅ Matched:", f"[bold green]{len(matches)}[/bold green]")
    summary_table.add_row("❌ Failed:", f"[bold red]{len(failed)}[/bold red]")
    summary_table.add_row("📈 Success Rate:", f"[bold cyan]{success_rate:.1f}%[/bold cyan]")

    if matches:
        avg_bitrate = sum(m.audio_bitrate for m in matches) / len(matches)
        avg_similarity = sum(m.title_similarity for m in matches) / len(matches)
        summary_table.add_row("🎧 Avg Bitrate:", f"[bold yellow]{avg_bitrate:.0f}kbps[/bold yellow]")
        summary_table.add_row("🎯 Avg Match:", f"[bold]{avg_similarity:.0%}[/bold]")

    console.print(Panel(summary_table, title="[bold]📋 RESULTS[/bold]", border_style="green"))

    # Output table if verbose
    if verbose and matches:
        console.print()
        table = Table(
            title="[bold]🎬 YouTube Matches[/bold]",
            border_style="yellow",
            header_style="bold magenta",
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Spotify Track", style="cyan", max_width=35)
        table.add_column("YouTube Match", style="green", max_width=40)
        table.add_column("Quality", style="yellow", justify="right")
        table.add_column("Match", style="bold", justify="right")

        for i, m in enumerate(matches, 1):
            quality_color = "green" if m.audio_bitrate >= 256 else "yellow" if m.audio_bitrate >= 128 else "red"
            table.add_row(
                str(i),
                m.track.search_query[:35],
                m.youtube_result.title[:40],
                f"[{quality_color}]{m.audio_bitrate:.0f}kbps[/{quality_color}]",
                f"{m.title_similarity:.0%}",
            )

        console.print(table)

    # Print URLs if not verbose
    if not verbose and matches:
        console.print()
        console.print(Panel("[bold]🔗 YouTube URLs[/bold]", border_style="blue"))
        for m in matches:
            console.print(f"  [blue]{m.youtube_result.url}[/blue]")

    # Export
    if output:
        output_path = Path(output)
        exporter = Exporter()
        try:
            exporter.export(matches, output_path)
            console.print()
            console.print(
                Panel(
                    f"[green]✓[/green] Exported [bold]{len(matches)}[/bold] matches to "
                    f"[cyan]{output}[/cyan]\n\n"
                    f"[dim]Download with:[/dim]\n"
                    f"  [bold]yt-dlp -x --audio-format mp3 -a {output}[/bold]",
                    title="[bold]💾 EXPORTED[/bold]",
                    border_style="green",
                )
            )
        except ValueError as e:
            console.print(Panel(f"[red]✗[/red] {e}", title="Export Error", border_style="red"))
            sys.exit(1)

    console.print()
    console.print("[dim]━" * 78 + "[/dim]")
    console.print("[dim]Thanks for using Spotify→YouTube! 🎵[/dim]", justify="center")


if __name__ == "__main__":
    main()
