"""Command-line interface for SpotifyToYouTube."""

import click


@click.group()
@click.version_option()
def main() -> None:
    """Fetch Spotify liked songs and find highest quality YouTube matches."""
    pass


if __name__ == "__main__":
    main()
