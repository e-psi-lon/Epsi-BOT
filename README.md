# Epsi-BOT

[![License](https://img.shields.io/github/license/e-psi-lon/Epsi-BOT)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/downloads/)
[![Pycord Version](https://img.shields.io/badge/py--cord-2.6.1-blue)](https://docs.pycord.dev/en/stable/)
[![Activity](https://img.shields.io/github/commit-activity/m/e-psi-lon/Epsi-BOT/dev)](https://github.com/e-psi-lon/Epsi-BOT/graphs/commit-activity)

## Database Schema

The bot uses MySQL for data persistence. You need to provide all the informations regarding how to connect to it in the environment variables.

### Core Tables

**Common Elements** — Common fields used across multiple tables

| CREATED_AT | UPDATED_AT |
|------------|------------|
| DATETIME   | DATETIME   |

**Server** — Discord guild settings

| SERVER_ID (PK) | LOOP_SONG | LOOP_QUEUE | RANDOM  | VOLUME  | POSITION |
|----------------|-----------|------------|---------|---------|----------|
| INTEGER        | BOOLEAN   | BOOLEAN    | BOOLEAN | INTEGER | INTEGER  |

**Song** — Audio track information

| SONG_ID (PK) | NAME    | URL (UQ) |
|--------------|---------|----------|
| INTEGER      | VARCHAR | TEXT     |

**User** — Discord user mapping

| ASKER_ID (PK) | DISCORD_ID (UQ) |
|---------------|-----------------|
| INTEGER       | INTEGER         |

### Playlists

**Playlist** — Named collections of songs

| PLAYLIST_ID (PK) | NAME    |
|------------------|---------|
| INTEGER          | VARCHAR |

**PlaylistSong** — Playlist song assignments

| PLAYLIST_ID (FK) | SONG_ID (FK) | POSITION | ASKER (FK) |
|------------------|--------------|----------|------------|
| INTEGER          | INTEGER      | INTEGER  | INTEGER    |

### Relationships

**ServerPlaylist** — Server playlist assignments

| SERVER_ID (FK) | PLAYLIST_ID (FK) |
|----------------|------------------|
| INTEGER        | INTEGER          |

**UserPlaylist** — User playlist ownership

| USER_ID (FK) | PLAYLIST_ID (FK) |
|--------------|------------------|
| INTEGER      | INTEGER          |

**Queue** — Server song queue

| SERVER_ID (FK) | SONG_ID (FK) | ASKER (FK) | POSITION |
|----------------|--------------|------------|----------|
| INTEGER        | INTEGER      | INTEGER    | INTEGER  |

**SongListenCount** — Play count tracking

| SONG_ID (FK) | COUNT   |
|--------------|---------|
| INTEGER      | INTEGER |

Legend:

- PK: Primary Key
- FK: Foreign Key
- UQ: Unique Constraint

## Development Setup

### Prerequisites

- Python 3.13+
- Python development tools (usually python3-dev or python3-devel)
- FFmpeg
- Libffi-dev (or libffi-devel)
- MySQL (SQLite if you plan to run unit tests)
- Memcached
- (Optional) Uses [`uv`](https://docs.astral.sh/uv) for easy dependency management and build

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/e-psi-lon/Epsi-BOT.git
   cd Epsi-Bot
   ```

2. Create and fill in the `.env` file based on the example:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and settings
   ```

3. Install the bot using one of these methods:

   ```bash
   # Using uv (recommended)
   uv pip install .
   
   # Using standard pip
   python -m pip install .
   # or
   pip install .
   ```

4. For development, install in editable mode:
   ```bash
   uv pip install -e ".[dev]"
   ```

### Running the Bot

```bash
uv run -m epsi_bot
# or
python -m epsi_bot
```

## Contributors

[![Contributors](https://contrib.rocks/image?repo=e-psi-lon/Epsi-BOT)](https://github.com/e-psi-lon/Epsi-BOT/graphs/contributors)

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
