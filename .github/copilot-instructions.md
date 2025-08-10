# Copilot Instructions for Epsi-BOT

**⚠️ IMPORTANT: ALWAYS use English for all code, comments, documentation, commit messages, and communication. This is a strict requirement.**

## Architecture Overview
Epsi-BOT is a Discord music bot written in Python with a dual-process architecture:
- **Bot Process** (`epsi_bot/bot/`): Discord bot logic using Pycord 2.6.1, organized in cogs (admin, playlist, queue_related, etc.)
- **Panel Process** (`epsi_bot/panel/`): Quart-based web admin panel with Discord OAuth2 authentication
- **Shared Utilities** (`epsi_bot/utils/`): Common components including audio processing, IPC, caching, and Tortoise ORM models

The processes communicate via custom IPC using multiprocessing queues (`epsi_bot/utils/ipc.py`). Memcached is used separately for session storage and caching. Data persistence uses MySQL with Tortoise ORM for async database operations.

## Development Workflows
- **Installation**: `uv pip install .` (recommended) or `python -m pip install .`. Dev mode: `uv pip install -e ".[dev]"`
- **Startup**: `uv run -m epsi_bot` or `python -m epsi_bot` (starts both bot and panel processes)
- **Configuration**: Copy `.env.example` to `.env` and configure database, Discord tokens, and Memcached settings
- **Testing**: `pytest tests/` for unit tests
- **Dependencies**: FFmpeg (audio processing), Memcached (caching), MySQL, libffi-dev

## Key Architecture Patterns
- **Multi-process Setup**: Panel spawns bot as separate process via `aiomultiprocess.Process` in `app.py:startup()`
- **IPC Communication**: Custom message-based IPC with request/response pattern. Panel requests guild data via `ipc.request("guilds", user_id=X)`
- **Database Context**: Use `@database_context` decorator or manual Tortoise init/close for DB operations outside main app lifecycle
- **Cog Structure**: Each cog in `epsi_bot/bot/cogs/` handles specific functionality (queue_related.py, playlist.py, admin.py, etc.)
- **Audio Pipeline**: YouTube download → FFmpeg conversion → Discord audio source via `epsi_bot/utils/audio.py`
- **Error Handling**: Centralized error handlers in bot.py send embed notifications to command issuer and bot owner

## Panel-Specific Patterns
- **Authentication**: Discord OAuth2 flow in `routes/auth.py` stores tokens in Quart sessions
- **Route Organization**: Blueprints in `epsi_bot/panel/routes/` (main.py, server.py, admin.py, auth.py)
- **Templates**: Jinja2 templates in `templates/` directory with Bootstrap-based styling
- **Discord API Integration**: `services/discord_api.py` handles Discord REST API calls for user/guild data

## Database Patterns
- **Models**: All in `epsi_bot/utils/models.py` extending `BaseModel` with auto-timestamps
- **Key Relations**: Server→Queue (1:N), Playlist→PlaylistSong→Song (M:N), User→Playlist (M:N)
- **ORM Usage**: Tortoise ORM with async/await, use `.prefetch_related()` for joins
- **Connection Management**: Always close connections with `await connections.close_all()` after operations

## Audio & Caching
- **YouTube Integration**: `pytubefix` for download, FFmpeg for format conversion
- **Audio Cache**: Custom `AudioCache` class manages temporary audio files with TTL
- **Memcached**: Used for session storage and caching frequently accessed data
- **Background Tasks**: Auto-update top 5 songs every 36 hours, git auto-update every 5 hours on main branch

## Essential Files
- `epsi_bot/__main__.py`: Entry point, starts Panel which spawns Bot process  
- `epsi_bot/bot/bot.py`: Bot initialization, cog loading, IPC handlers, error handling
- `epsi_bot/panel/app.py`: Panel class extending Quart, process management, IPC setup
- `epsi_bot/utils/models.py`: Tortoise ORM models with relationships
- `epsi_bot/utils/ipc.py`: Custom IPC implementation for bot↔panel communication
- `pyproject.toml`: Dependencies including py-cord, tortoise-orm, quart, aiomultiprocess

## Adding Features
- **Discord Commands**: Create new cog in `epsi_bot/bot/cogs/`, register in bot.py's cog loading loop
- **Panel Routes**: Add blueprint to `epsi_bot/panel/routes/`, import in `routes/__init__.py`
- **Database Models**: Extend `BaseModel` in `models.py`, use Tortoise field types
- **IPC Handlers**: Register with `@bot.handle("event_name")` in bot.py for panel→bot communication
