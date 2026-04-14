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
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from spotifytoyoutube.cache import MatchCache
from spotifytoyoutube.export import Exporter, load_matches_from_json
from spotifytoyoutube.matcher import MatchResult, TrackMatcher
from spotifytoyoutube.spotify_auth import SpotifyAuthenticator
from spotifytoyoutube.spotify_client import SpotifyClient, Track
from spotifytoyoutube.tagger import tag_file
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


def interactive_wizard() -> None:
    """Interactive wizard for matching Spotify songs to YouTube."""
    show_banner()

    console.print(
        Panel(
            "[bold cyan]Welcome to the Interactive Setup![/bold cyan]\n\n"
            "I'll ask you a few questions to get started.\n"
            "Press [bold]Ctrl+C[/bold] anytime to exit.",
            border_style="cyan",
        )
    )
    console.print()

    # Check credentials first
    try:
        client_id, client_secret = get_spotify_credentials()
    except click.ClickException:
        console.print(
            Panel(
                "[red]✗ Spotify credentials not found![/red]\n\n"
                "Please set these environment variables:\n"
                "  [cyan]export SPOTIFY_CLIENT_ID='your_client_id'[/cyan]\n"
                "  [cyan]export SPOTIFY_CLIENT_SECRET='your_client_secret'[/cyan]\n\n"
                "[dim]Get credentials at: https://developer.spotify.com/dashboard[/dim]",
                title="Setup Required",
                border_style="red",
            )
        )
        sys.exit(1)

    console.print("[green]✓[/green] Spotify credentials found!\n")

    # Question 1: Number of songs
    console.print("[bold]📊 How many songs would you like to match?[/bold]")
    console.print("[dim]  Suggestions: 10 (quick test), 50 (default), 100, 500, or custom[/dim]")
    limit = IntPrompt.ask(
        "  Number of songs",
        default=50,
        console=console,
    )
    console.print()

    # Question 2: Speed mode
    console.print("[bold]⚡ Speed mode[/bold]")
    console.print("[dim]  Fast mode searches YouTube in parallel (much faster!)[/dim]")
    fast = Confirm.ask("  Enable fast mode?", default=True, console=console)
    console.print()

    # Question 3: Workers (if fast mode)
    workers = 8
    if fast:
        console.print("[bold]👷 Parallel workers[/bold]")
        console.print("[dim]  More workers = faster, but may hit rate limits[/dim]")
        console.print("[dim]  Suggestions: 4 (gentle), 8 (balanced), 16 (aggressive)[/dim]")
        workers = IntPrompt.ask(
            "  Number of workers",
            default=8,
            console=console,
        )
        console.print()

    # Question 4: Verbose output
    console.print("[bold]📝 Verbose output[/bold]")
    console.print("[dim]  Shows detailed progress and match information[/dim]")
    verbose = Confirm.ask("  Enable verbose output?", default=True, console=console)
    console.print()

    # Question 5: Export options
    console.print("[bold]💾 Export results[/bold]")
    console.print("[dim]  Save matches to a file for downloading later[/dim]")
    export = Confirm.ask("  Export to file?", default=True, console=console)

    output_path = None
    if export:
        console.print()
        console.print("[bold]📁 Export format[/bold]")
        console.print("  [cyan]1.[/cyan] m3u  - Playlist file (works with yt-dlp)")
        console.print("  [cyan]2.[/cyan] json - Full data export")
        console.print("  [cyan]3.[/cyan] csv  - Spreadsheet format")
        console.print("  [cyan]4.[/cyan] txt  - Simple URL list")

        format_choice = Prompt.ask(
            "  Choose format",
            choices=["1", "2", "3", "4", "m3u", "json", "csv", "txt"],
            default="1",
            console=console,
        )

        format_map = {"1": "m3u", "2": "json", "3": "csv", "4": "txt"}
        file_format = format_map.get(format_choice, format_choice)

        default_filename = f"spotify_matches.{file_format}"
        console.print()
        output_path = Prompt.ask(
            "  Filename",
            default=default_filename,
            console=console,
        )

    console.print()

    # Question 6: Caching
    console.print("[bold]🗄️  Caching[/bold]")
    console.print("[dim]  Cache results to speed up future runs (recommended)[/dim]")
    use_cache = Confirm.ask("  Enable caching?", default=True, console=console)
    console.print()

    # Summary
    summary_table = Table.grid(padding=(0, 2))
    summary_table.add_column(style="cyan")
    summary_table.add_column(style="bold")

    summary_table.add_row("Songs to match:", str(limit))
    summary_table.add_row("Speed mode:", f"{'⚡ Fast' if fast else '🐢 Normal'} ({workers} workers)" if fast else "🐢 Normal")
    summary_table.add_row("Verbose:", "Yes" if verbose else "No")
    summary_table.add_row("Export:", output_path if output_path else "No")
    summary_table.add_row("Caching:", "Enabled" if use_cache else "Disabled")

    console.print(Panel(summary_table, title="[bold]📋 Your Settings[/bold]", border_style="green"))
    console.print()

    if not Confirm.ask("[bold]Ready to start?[/bold]", default=True, console=console):
        console.print("\n[dim]Cancelled. Run again when you're ready![/dim]")
        return

    console.print()
    console.print("[dim]─" * 60 + "[/dim]")
    console.print()

    # Run the match command with selected options
    run_match(
        limit=limit,
        output=output_path,
        duration_threshold=10,
        verbose=verbose,
        fast=fast,
        workers=workers,
        no_cache=not use_cache,
        show_banner_=False,  # Already shown at wizard start
    )


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def main(ctx: click.Context) -> None:
    """Fetch Spotify liked songs and find highest quality YouTube matches."""
    if ctx.invoked_subcommand is None:
        # No subcommand provided, run interactive wizard
        interactive_wizard()


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


@main.command("clear-cache")
def clear_cache() -> None:
    """Clear all cached YouTube match results."""
    show_banner(mini=True)
    console.print()

    cache = MatchCache()
    cache_dir = cache.cache_dir

    # Count files before clearing
    cache_files = list(cache_dir.glob("*.json"))
    count = len(cache_files)

    if count == 0:
        console.print(
            Panel(
                "[dim]Cache is already empty.[/dim]",
                title="Cache Status",
                border_style="dim",
            )
        )
        return

    cache.clear()
    console.print(
        Panel(
            f"[green]✓[/green] Cleared [bold]{count}[/bold] cached entries.\n\n"
            f"[dim]Location: {cache_dir}[/dim]",
            title="Cache Cleared",
            border_style="green",
        )
    )


@main.command()
@click.option("--input", "-i", "input_file", type=click.Path(exists=True), help="Input file with YouTube URLs (.txt or .m3u)")
@click.option("--output-dir", "-o", default=None, help="Output directory for downloads")
@click.option("--format", "-f", "audio_format", default=None, help="Audio format (mp3, opus, m4a, wav)")
@click.option("--limit", "-l", default=None, type=int, help="Number of songs to match (if no input file)")
@click.option("--keep-video", is_flag=True, help="Keep video file instead of extracting audio")
@click.option("--no-tags", is_flag=True, help="Skip embedding metadata tags in downloaded files")
@click.option("--interactive/--no-interactive", default=None, help="Force interactive/non-interactive mode")
def download(
    input_file: str | None,
    output_dir: str | None,
    audio_format: str | None,
    limit: int | None,
    keep_video: bool,
    no_tags: bool,
    interactive: bool | None,
) -> None:
    """Download matched songs as audio files."""
    import subprocess

    show_banner(mini=True)
    console.print()

    # Determine if we should run interactive mode
    # Interactive if: explicitly requested, OR no options provided
    run_interactive = interactive is True or (
        interactive is None
        and input_file is None
        and output_dir is None
        and audio_format is None
        and limit is None
        and not keep_video
        and not no_tags
    )

    if run_interactive:
        console.print(
            Panel(
                "[bold cyan]Download Setup[/bold cyan]\n\n"
                "I'll help you download your Spotify songs as audio files.",
                border_style="cyan",
            )
        )
        console.print()

        # Question 1: Source
        console.print("[bold]📂 Where should I get the songs from?[/bold]")
        console.print("  [cyan]1.[/cyan] Match from Spotify (fetch liked songs and find YouTube matches)")
        console.print("  [cyan]2.[/cyan] Use existing playlist file (.txt or .m3u)")

        source_choice = Prompt.ask(
            "  Choose source",
            choices=["1", "2"],
            default="1",
            console=console,
        )
        console.print()

        if source_choice == "2":
            input_file = Prompt.ask(
                "  Path to playlist file",
                console=console,
            )
            if not Path(input_file).exists():
                console.print(f"[red]File not found: {input_file}[/red]")
                sys.exit(1)
        else:
            # Question: How many songs
            console.print("[bold]🎵 How many songs to download?[/bold]")
            console.print("[dim]  Suggestions: 10 (quick), 25, 50, 100[/dim]")
            limit = IntPrompt.ask(
                "  Number of songs",
                default=20,
                console=console,
            )
            console.print()

        # Question 2: Output directory
        console.print("[bold]📁 Where should I save the files?[/bold]")
        default_dir = "~/Music/SpotifyDownloads"
        output_dir = Prompt.ask(
            "  Output directory",
            default=default_dir,
            console=console,
        )
        console.print()

        # Question 3: Audio format
        console.print("[bold]🎧 What audio format?[/bold]")
        console.print("  [cyan]1.[/cyan] mp3  - Universal compatibility (recommended)")
        console.print("  [cyan]2.[/cyan] opus - Best quality/size ratio")
        console.print("  [cyan]3.[/cyan] m4a  - Apple/iTunes compatible")
        console.print("  [cyan]4.[/cyan] wav  - Lossless (large files)")

        format_choice = Prompt.ask(
            "  Choose format",
            choices=["1", "2", "3", "4", "mp3", "opus", "m4a", "wav"],
            default="1",
            console=console,
        )
        format_map = {"1": "mp3", "2": "opus", "3": "m4a", "4": "wav"}
        audio_format = format_map.get(format_choice, format_choice)
        console.print()

        # Question: Metadata tagging (only when using Spotify source)
        if not input_file:
            console.print("[bold]🏷️  Embed metadata tags?[/bold]")
            console.print("[dim]  Writes artist, album, genre, and cover art into each file[/dim]")
            embed_tags = Confirm.ask("  Embed tags?", default=True, console=console)
            no_tags = not embed_tags
            console.print()

        # Summary
        summary_table = Table.grid(padding=(0, 2))
        summary_table.add_column(style="cyan")
        summary_table.add_column(style="bold")

        if input_file:
            summary_table.add_row("Source:", f"File: {input_file}")
        else:
            summary_table.add_row("Source:", f"Spotify ({limit} songs)")
        summary_table.add_row("Output:", output_dir)
        summary_table.add_row("Format:", audio_format)
        if not input_file:
            summary_table.add_row("Tags:", "Yes" if not no_tags else "No")

        console.print(Panel(summary_table, title="[bold]📋 Download Settings[/bold]", border_style="green"))
        console.print()

        if not Confirm.ask("[bold]Start download?[/bold]", default=True, console=console):
            console.print("\n[dim]Cancelled.[/dim]")
            return

        console.print()
        console.print("[dim]─" * 60 + "[/dim]")
        console.print()

    # Apply defaults for non-interactive mode
    if output_dir is None:
        output_dir = "~/Music/SpotifyDownloads"
    if audio_format is None:
        audio_format = "mp3"
    if limit is None:
        limit = 20

    # Expand ~ in path
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    match_results: list[MatchResult] = []

    if input_file:
        input_path = Path(input_file)
        if input_path.suffix.lower() == ".json":
            # Load full match data from JSON (preserves metadata for tagging)
            console.print(f"[dim]Loading matches from {input_file}...[/dim]")
            match_results = load_matches_from_json(input_path)
            console.print(
                f"[green]✓[/green] Loaded [bold]{len(match_results)}[/bold] "
                f"matches with metadata\n"
            )
        else:
            # Read bare URLs from txt/m3u
            console.print(f"[dim]Reading URLs from {input_file}...[/dim]")
            with open(input_file) as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith("http"):
                        urls.append(line)
                    elif line and not line.startswith("#"):
                        if "youtube.com" in line or "youtu.be" in line:
                            urls.append(line)
            console.print(f"[green]✓[/green] Found [bold]{len(urls)}[/bold] URLs\n")
    else:
        # Run the match process first
        console.print(
            Panel(
                "[bold cyan]No input file provided[/bold cyan]\n"
                f"Will match [bold]{limit}[/bold] songs from Spotify first...",
                border_style="cyan",
            )
        )
        console.print()

        try:
            client_id, client_secret = get_spotify_credentials()
        except click.ClickException as e:
            console.print(Panel(f"[red]✗[/red] {e.message}", title="Error", border_style="red"))
            sys.exit(1)

        # Setup and run matcher
        cache = MatchCache()
        authenticator = SpotifyAuthenticator(client_id=client_id, client_secret=client_secret)
        sp = authenticator.get_client()
        spotify_client = SpotifyClient(sp)
        youtube_searcher = YouTubeSearcher(quiet=True)
        matcher = TrackMatcher(youtube_searcher, cache=cache, skip_detailed_info=True)

        tracks: list[Track] = []
        with console.status("[bold green]🎵 Loading liked songs...[/bold green]", spinner="dots"):
            for track in spotify_client.get_liked_songs(max_tracks=limit):
                tracks.append(track)

        console.print(f"[green]✓[/green] Loaded [bold]{len(tracks)}[/bold] tracks")

        with console.status("[bold green]🎵 Enriching tracks with metadata...[/bold green]", spinner="dots"):
            spotify_client.enrich_tracks(tracks)

        console.print("[green]✓[/green] Enriched tracks with audio features & genres\n")

        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("⚡ Matching songs...", total=len(tracks))

            def on_complete(track: Track, result: MatchResult | None) -> None:
                progress.advance(task)
                if result:
                    match_results.append(result)

            matcher.find_matches_parallel(tracks, max_workers=8, on_complete=on_complete)

        console.print(f"\n[green]✓[/green] Matched [bold]{len(match_results)}[/bold] songs\n")

    total_items = len(match_results) or len(urls)
    if total_items == 0:
        console.print("[red]No URLs to download![/red]")
        return

    # Filename template - clean format
    output_template = str(output_path / "%(title)s.%(ext)s")

    if match_results and not no_tags:
        # Per-file download + tag loop (we have Spotify metadata)
        console.print(
            Panel(
                f"[bold yellow]📥 Downloading & tagging {len(match_results)} songs[/bold yellow]\n\n"
                f"[dim]Format:[/dim] {audio_format}\n"
                f"[dim]Output:[/dim] {output_path}\n"
                f"[dim]Tags:[/dim]  Enabled",
                border_style="yellow",
            )
        )
        console.print()

        download_ok = 0
        download_fail = 0
        tag_ok = 0
        tag_fail = 0

        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            dl_task = progress.add_task("📥 Downloading...", total=len(match_results))

            for mr in match_results:
                progress.update(
                    dl_task,
                    description=f"📥 [cyan]{mr.track.artist}[/cyan] - {mr.track.name[:30]}",
                )
                url = mr.youtube_result.url
                cmd = [
                    "yt-dlp", "--no-warnings", "-o", output_template,
                    "--print", "after_move:filepath",
                    "--quiet",
                ]
                if not keep_video:
                    cmd.extend(["-x", "--audio-format", audio_format])
                cmd.append(url)

                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, check=False,
                    )
                    if result.returncode != 0:
                        download_fail += 1
                        progress.advance(dl_task)
                        continue

                    filepath_str = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
                    if not filepath_str or not Path(filepath_str).exists():
                        download_fail += 1
                        progress.advance(dl_task)
                        continue

                    download_ok += 1
                    filepath = Path(filepath_str)

                    if tag_file(filepath, mr, audio_format):
                        tag_ok += 1
                    else:
                        tag_fail += 1

                except FileNotFoundError:
                    console.print(
                        Panel(
                            "[red]✗[/red] yt-dlp not found!\n\n"
                            "[dim]Install with:[/dim]\n"
                            "  [bold]pip install yt-dlp[/bold]",
                            title="Error",
                            border_style="red",
                        )
                    )
                    sys.exit(1)

                progress.advance(dl_task)

        console.print()
        tag_info = f"\n[dim]Tagged:[/dim] {tag_ok}/{download_ok}"
        if tag_fail:
            tag_info += f" [yellow]({tag_fail} tag failures)[/yellow]"

        if download_fail == 0:
            console.print(
                Panel(
                    f"[green]✓[/green] Downloaded [bold]{download_ok}[/bold] songs to:\n"
                    f"  [cyan]{output_path}[/cyan]{tag_info}",
                    title="[bold]COMPLETE[/bold]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"[yellow]⚠[/yellow] Downloaded {download_ok}/{len(match_results)} songs.\n"
                    f"Check [cyan]{output_path}[/cyan] for downloaded files.{tag_info}\n\n"
                    f"[dim]If you see ffmpeg errors, install it with:[/dim]\n"
                    f"  [bold]sudo apt install ffmpeg[/bold]",
                    title="[bold]PARTIAL[/bold]",
                    border_style="yellow",
                )
            )
    else:
        # Batch download (input file or --no-tags)
        all_urls = [mr.youtube_result.url for mr in match_results] if match_results else urls
        console.print(
            Panel(
                f"[bold yellow]📥 Downloading {len(all_urls)} songs[/bold yellow]\n\n"
                f"[dim]Format:[/dim] {audio_format}\n"
                f"[dim]Output:[/dim] {output_path}",
                border_style="yellow",
            )
        )
        console.print()

        cmd = ["yt-dlp", "--no-warnings", "-o", output_template]

        if not keep_video:
            cmd.extend(["-x", "--audio-format", audio_format])

        cmd.append("--progress")
        cmd.extend(all_urls)

        try:
            console.print("[dim]Starting downloads...[/dim]\n")
            result = subprocess.run(cmd, check=False)

            console.print()
            if result.returncode == 0:
                console.print(
                    Panel(
                        f"[green]✓[/green] Downloaded [bold]{len(all_urls)}[/bold] songs to:\n"
                        f"  [cyan]{output_path}[/cyan]",
                        title="[bold]COMPLETE[/bold]",
                        border_style="green",
                    )
                )
            else:
                console.print(
                    Panel(
                        f"[yellow]⚠[/yellow] Download completed with some errors.\n"
                        f"Check [cyan]{output_path}[/cyan] for downloaded files.\n\n"
                        f"[dim]If you see ffmpeg errors, install it with:[/dim]\n"
                        f"  [bold]sudo apt install ffmpeg[/bold]",
                        title="[bold]PARTIAL[/bold]",
                        border_style="yellow",
                    )
                )
        except FileNotFoundError:
            console.print(
                Panel(
                    "[red]✗[/red] yt-dlp not found!\n\n"
                    "[dim]Install with:[/dim]\n"
                    "  [bold]pip install yt-dlp[/bold]",
                    title="Error",
                    border_style="red",
                )
            )
            sys.exit(1)


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


def run_match(
    limit: int,
    output: str | None,
    duration_threshold: int,
    verbose: bool,
    fast: bool,
    workers: int,
    no_cache: bool,
    show_banner_: bool = True,
) -> None:
    """Core match logic - find YouTube matches for liked songs."""
    if show_banner_:
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

    console.print(f"    [green]✓[/green] Loaded [bold]{len(tracks)}[/bold] tracks from Spotify")

    with console.status("[bold green]🎵 Enriching tracks with metadata...[/bold green]", spinner="dots"):
        spotify_client.enrich_tracks(tracks)

    console.print("    [green]✓[/green] Enriched tracks with audio features & genres\n")

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

            # Show appropriate download instructions based on format
            ext = output_path.suffix.lower()
            if ext in (".txt", ".m3u"):
                download_hint = (
                    f"[dim]Download as MP3 with:[/dim]\n"
                    f"  [bold]yt-dlp -x --audio-format mp3 -a {output}[/bold]"
                )
            elif ext == ".json":
                download_hint = "[dim]JSON format for data processing/backup[/dim]"
            elif ext == ".csv":
                download_hint = "[dim]CSV format for spreadsheets[/dim]"
            else:
                download_hint = ""

            console.print(
                Panel(
                    f"[green]✓[/green] Exported [bold]{len(matches)}[/bold] matches to "
                    f"[cyan]{output}[/cyan]"
                    + (f"\n\n{download_hint}" if download_hint else ""),
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
    run_match(
        limit=limit,
        output=output,
        duration_threshold=duration_threshold,
        verbose=verbose,
        fast=fast,
        workers=workers,
        no_cache=no_cache,
    )


if __name__ == "__main__":
    main()
