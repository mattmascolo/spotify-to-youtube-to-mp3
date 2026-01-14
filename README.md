# SpotifyToYouTube

Fetch your Spotify liked songs and find the highest quality YouTube matches.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Set credentials
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"

# Authenticate
spotifytoyoutube auth

# Fetch liked songs
spotifytoyoutube fetch --limit 100

# Find YouTube matches
spotifytoyoutube match --limit 50 --output playlist.m3u
```
