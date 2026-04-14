# Spotify to YouTube to MP3

A CLI tool that fetches your Spotify liked songs, playlists, albums, or artists and downloads the highest-quality YouTube (or SoundCloud fallback) audio for each track, with Spotify metadata embedded and files organized into Artist/Album folders.

![Screenshot](assets/screenshot.png)

## Features

- Paste **any Spotify URL** — track, album, playlist, artist, or liked songs — and download it in one command
- OAuth to Spotify with token caching (no re-login after the first run)
- Multi-source matching: YouTube first, SoundCloud automatic fallback when YouTube has no good match
- **ISRC verification**: when the YouTube video description includes the Spotify ISRC, the match is guaranteed to be the same recording
- Quality-first scoring (60% audio bitrate, 30% title similarity, 10% duration match, +20% when ISRC-verified)
- Parallel searching for fast results
- Persistent result cache so repeat runs are instant
- Downloads auto-organize into `Artist/Album/NN - Title.mp3` — library-ready for Plex/Jellyfin/Navidrome
- Metadata embedding: title, artist, album, year, track number, genre, cover art, across MP3/M4A/Opus/WAV
- Export-only mode: produce playlist files in M3U, JSON, CSV, or TXT without downloading

## Installation

### Prerequisites

- Python 3.11+
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [ffmpeg](https://ffmpeg.org/) (for audio extraction/conversion)

```bash
# Clone the repository
git clone https://github.com/yourusername/spotifytoyoutube.git
cd spotifytoyoutube

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .

# Install ffmpeg (Ubuntu/Debian)
sudo apt install ffmpeg
```

After `pip install -e .`, two CLI commands are available in the venv:

- `spotdownload` — recommended, short and memorable
- `spotifytoyoutube` — original long form, still works

To use `spotdownload` from any directory without activating the venv, add a tiny wrapper to `~/.local/bin`:

```bash
cat > ~/.local/bin/spotdownload <<'EOF'
#!/bin/sh
exec /absolute/path/to/spotifytoyoutube/.venv/bin/spotdownload "$@"
EOF
chmod +x ~/.local/bin/spotdownload
```

### Spotify API Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new application
3. Add `http://127.0.0.1:8888/callback` to the Redirect URIs
4. Copy your Client ID and Client Secret

Store them in a `.env` file at the project root (gitignored, never committed):

```bash
cat > .env <<'EOF'
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
EOF
chmod 600 .env
```

The CLI auto-loads `.env` from the current working directory or the repo root. You can still use environment variables if you prefer — they override the file.

## Usage

### Quickstart: one command, any Spotify URL

```bash
# Download an album
spotdownload grab https://open.spotify.com/album/<id>

# Download a playlist, capped at 20 tracks
spotdownload grab https://open.spotify.com/playlist/<id> --limit 20

# Download an artist's top tracks
spotdownload grab https://open.spotify.com/artist/<id>

# Download a single track
spotdownload grab spotify:track:<id>

# Download your Spotify "Liked Songs"
spotdownload grab liked --limit 50
```

URLs, Spotify URIs (`spotify:album:...`), `intl-xx` regional prefixes, and `?si=...` share query strings all work.

### Interactive wizard

Run with no subcommand for a guided flow:

```bash
spotdownload            # match & export wizard
spotdownload download   # match & download wizard
```

### Individual commands

```bash
# Authenticate and verify credentials
spotdownload auth

# Fetch your liked songs (or a playlist)
spotdownload fetch --limit 100
spotdownload fetch --playlist <playlist_id>

# Find YouTube matches and export to a playlist file
spotdownload match --limit 50 --fast --verbose
spotdownload match --limit 50 -o playlist.m3u

# Download and tag files
spotdownload download --limit 20 -o ~/Music/Spotify
spotdownload download --playlist <playlist_id> --limit 20

# Clear the result cache
spotdownload clear-cache
```

### Options

#### `grab` command — paste any URL and go

| Option | Description |
|--------|-------------|
| `URL` | Spotify URL, URI, or `liked` sentinel (positional, required) |
| `-o, --output-dir` | Download directory (default: `~/Music/SpotifyDownloads`) |
| `-f, --format` | Audio format: `mp3`, `opus`, `m4a`, `wav` (default: `mp3`) |
| `-l, --limit` | Cap the number of tracks fetched |
| `--no-tags` | Skip embedding metadata tags |
| `--organize/--no-organize` | Organize into Artist/Album folders (default: on) |
| `--keep-video` | Keep the video file instead of extracting audio |

#### `match` command

| Option | Description |
|--------|-------------|
| `-l, --limit` | Number of tracks to match |
| `-o, --output` | Export file (`.txt`, `.m3u`, `.json`, `.csv`) |
| `-f, --fast` | Enable parallel searching |
| `-w, --workers` | Parallel worker count (default: 8) |
| `-v, --verbose` | Detailed progress output |
| `-p, --playlist` | Match from a playlist ID instead of liked songs (repeatable) |
| `--no-cache` | Disable result caching |

#### `download` command

| Option | Description |
|--------|-------------|
| `-i, --input` | Input playlist file (`.txt`, `.m3u`, `.json`) |
| `-o, --output-dir` | Download directory (default: `~/Music/SpotifyDownloads`) |
| `-f, --format` | Audio format: `mp3`, `opus`, `m4a`, `wav` |
| `-l, --limit` | Tracks to match when no input file is given |
| `--no-tags` | Skip metadata tagging |
| `--organize/--no-organize` | Organize into Artist/Album folders (default: on) |
| `-p, --playlist` | Match from a playlist ID instead of liked songs (repeatable) |

## How It Works

1. **Parse** the Spotify URL into a `(kind, id)` resource (track / album / playlist / artist / liked).
2. **Authenticate** with Spotify via OAuth — manual paste flow, no local HTTP server needed, so port conflicts don't break auth. Token is cached.
3. **Fetch** the relevant tracks via the Spotify Web API and enrich them with audio features and genres.
4. **Match** each track against YouTube (and SoundCloud as a fallback), scoring candidates by audio bitrate, title similarity, and duration. When the Spotify track has an ISRC and the YouTube video description contains it, the match is marked `isrc_verified` and gets a scoring boost.
5. **Download** via `yt-dlp`, extracting the chosen audio format.
6. **Organize** each file into `<output>/<Artist>/<Album>/<NN> - <Title>.<ext>`.
7. **Tag** with Spotify metadata (title, artist, album, release year, track number, genre, cover art) via mutagen.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run with coverage
pytest --cov=spotifytoyoutube
```

## License

MIT
