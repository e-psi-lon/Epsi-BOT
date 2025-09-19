# Copilot Instructions for Epsi-BOT

**⚠️ IMPORTANT: ALWAYS use English for all code, comments, documentation, commit messages, and communication. This is a strict requirement.**

## Architecture Overview
Epsi-BOT is a Discord music bot written in Python 3.13+ with a sophisticated dual-process architecture:

### Core Processes
- **Panel Process** (`epsi_bot/panel/`): Primary Quart web application that spawns and manages the bot process
- **Bot Process** (`epsi_bot/bot/`): Discord bot using Pycord 2.6.1, organized in functional cogs
- **Shared Utilities** (`epsi_bot/utils/`): Common components for audio, IPC, database, caching, and data models

### External Dependencies
- **Memcached**: Session storage, audio caching, and IPC result caching
- **MySQL**: Primary database via Tortoise ORM (async operations)
- **FFmpeg**: Audio format conversion and processing
- **Docker**: Optional containerized deployment

## Process Architecture & Communication

### Startup Sequence
1. `__main__.py` creates Panel app and sets start time
2. Panel app initializes during `startup()` event:
   - Creates SQLite database if missing
   - Starts Memcached subprocess with custom stdout/stderr handling (`MemcachedStd`)
   - Spawns Bot process via `aiomultiprocess.Process`
   - Establishes bidirectional IPC channels

### IPC System (`epsi_bot/utils/ipc.py`)
- **Custom Implementation**: Uses multiprocessing Queues with async wrappers
- **Message Types**: EVENT, DATA, REQUEST, RESPONSE (via `MessageType` enum)
- **Request/Response Pattern**: Panel can request data from bot with timeout support
- **Error Handling**: Automatic future cancellation, timeout management, reconnection logic
- **Key IPC Channels**: `guilds`, `guild`, `user`, `connected_servers`, `voice_channels`

### Memcached Integration
- **Audio Cache**: Compressed audio files with TTL management and bulk operations
- **Session Storage**: Discord OAuth2 tokens and user data
- **IPC Caching**: Bot responses cached for 60 seconds to reduce latency
- **Custom Compression**: Base64 + zlib compression for audio data

## Bot Architecture

### Cog System
All cogs follow standard pattern with `setup(bot: Bot)` function:
- **admin.py**: Bot management, cog reloading, owner-only commands
- **channel.py**: Voice channel connection management 
- **help.py**: Custom help system with paginated embeds
- **listeners.py**: Event handlers (voice state changes, guild join/leave)
- **others.py**: Utility commands (ping, leave voice, etc.)
- **playlist.py**: Comprehensive playlist management (server/user types, YouTube import)
- **queue_related.py**: Queue manipulation (add, remove, skip, shuffle, loop modes)
- **state.py**: Audio playback control (play, pause, volume, recording)
- **todo.py**: Task management with user assignment

### Command Structure
- **Slash Commands**: Primary interface using Discord's application commands
- **Command Groups**: Nested commands using `SlashCommandGroup` (e.g., `/playlist create`)
- **Autocompletion**: Dynamic suggestions for playlists, songs, queues via utility functions
- **Error Handling**: Centralized error catching with embed responses to users and bot owner

### Background Tasks
- **Git Auto-Update**: Every 5 hours on main branch, checks remote and auto-restarts if needed
- **Top Songs Caching**: Every 36 hours, calculates top 5 most played songs and pre-caches them
- **Audio Pre-downloading**: Background bulk downloads for playlists to improve playback latency

## Database Architecture

### Model Hierarchy
All models extend `BaseModel` with automatic timestamps and enhanced features:

```
BaseModel (abstract)
├── Server: Server configurations (loop modes, volume, position)
├── User: Discord user mapping
├── Song: Audio tracks with unique URLs
├── Playlist: Named song collections
├── SongListenCount: Play count tracking
├── AudioReference (abstract): Position-based song references
│   ├── PlaylistSong: Songs within playlists
│   └── Queue: Server queue entries
└── PlaylistReference (abstract): Playlist ownership
    ├── ServerPlaylist: Server-owned playlists
    └── UserPlaylist: User-owned playlists
```

### Advanced Model Features
- **Auto-Positioning**: `AudioReference` subclasses automatically calculate position on save (transaction-safe/atomic)
- **Bulk Operations**: Efficient bulk creation for playlist imports and queue operations
- **Relationship Prefetching**: Extensive use of `prefetch_related()` for performance
- **Database Context Manager**: `async with database_context()` to manage connections to the database
- **Connection Pooling**: Automatic connection management with `connections.close_all()`

### Key Relationships
- Server ↔ Queue (1:N): Each server has one active queue
- Playlist ↔ PlaylistSong ↔ Song (M:N through junction): Many-to-many with position tracking
- User ↔ Playlist (M:N through PlaylistReference pattern): Supports both user and server ownership
- Song ↔ SongListenCount (1:1): Play count analytics

## Audio Processing Pipeline

### YouTube Integration
- **Library**: `pytubefix` for YouTube video/playlist processing
- **Stream Selection**: Automatic audio-only stream selection
- **Age Restriction**: Automatic detection and graceful handling
- **Duration Limits**: 3-hour maximum track length (`MAX_TRACK_LENGTH`)

### Audio Cache System (`epsi_bot/utils/cache.py`)
- **Intelligent Caching**: TTL-based with automatic refresh for popular tracks
- **Compression**: zlib + base64 encoding for storage efficiency
- **Bulk Downloads**: Concurrent download system for playlists
- **Cache Management**: Automatic cleanup and TTL updates for frequently accessed content

### Playback Architecture
- **FFmpeg Integration**: Dynamic audio conversion and processing
- **Volume Control**: Per-server volume with Discord PCM transformation
- **Queue Management**: Position tracking with loop modes (song, queue) and shuffle
- **Callback System**: Automatic song progression with error handling

### Recording Features
- **Multi-user Recording**: Simultaneous recording of multiple users in voice channels
- **Audio Merging**: FFmpeg-based stream merging with configurable formats
- **Format Support**: MP3, WAV, OGG, MP4 via `Sinks` enum
- **File Management**: Automatic cleanup and delivery via Discord attachments

## Panel Architecture

### Web Framework
- **Quart**: Async web framework with WebSocket support
- **Session Management**: Memcached-backed sessions with automatic token refresh
- **Template Engine**: Jinja2 with Bootstrap-based responsive design
- **Error Handling**: Comprehensive error pages and graceful degradation

### Authentication System (`epsi_bot/panel/routes/auth.py`)
- **Discord OAuth2**: Full OAuth2 flow with automatic token refresh
- **Timer Management**: Automatic token refresh scheduling via asyncio timers
- **Secure Logout**: Proper token revocation and session cleanup
- **Guild Filtering**: User-specific guild lists based on bot membership

### Route Organization
- **Blueprint Structure**: Modular routes with clear separation of concerns
- **Decorators**: `@login_required` and `@admin_required` for access control
- **Admin Panel**: Real-time dashboard with WebSocket updates for system monitoring
- **Server Management**: Per-server configuration with queue management

### Admin Dashboard Features
- **Real-time Monitoring**: WebSocket-based live updates every 30 seconds
- **Process Statistics**: CPU, memory, and thread monitoring for both processes
- **Cache Analytics**: Hit/miss ratios and memory usage visualization
- **Database Inspection**: Live table browsing with relationship navigation

## Security & Access Control

### Authentication Levels
1. **Public**: Index page and basic bot information
2. **Authenticated**: Panel access with Discord OAuth2 verification
3. **Admin**: Local network access only (`192.168.83.*` or `127.0.0.1`)

### Data Protection
- **Environment Variables**: All secrets stored in `.env` file
- **Session Security**: Secure session handling with proper cleanup
- **Token Management**: Automatic refresh and revocation
- **IP Restrictions**: Admin routes restricted to local network access

## Development Workflows

### Setup & Installation
```bash
# Recommended: UV package manager
uv pip install -e ".[dev]"  # Development mode
uv run -m epsi_bot           # Run application

# Alternative: Standard pip
python -m pip install -e ".[dev]"
python -m epsi_bot
```

### Configuration
```bash
# Copy template and configure
cp .env.example .env
# Required variables:
# TOKEN, PANEL_SECRET_KEY, CLIENT_SECRET
# DB_HOST, DB_PORT, DB_USER, DB_PASSWORD
# DB_NAME
```

### Testing & Quality
- **pytest**: Unit tests in `tests/` directory
- **mypy**: Type checking configuration in `mypy.ini`
- **Coverage**: Test coverage tracking via pytest-cov

## Deployment Architecture

### Docker Support
- **Multi-stage Build**: Optimized Docker image
- **Environment Handling**: Docker-specific environment file (`.env.docker`)
- **Port Configuration**: Default web panel on port 8080

### Dependencies
- **System**: FFmpeg, Memcached, MySQL/MariaDB
- **Python**: 3.13+ with modern async/await patterns
- **Libraries**: See `pyproject.toml` for complete dependency list

## Code Patterns & Conventions

### Error Handling
- **Embed Responses**: Consistent Discord embed formatting for errors
- **Graceful Degradation**: Fallback behaviors for external service failures
- **Logging**: Comprehensive logging with custom formatters and colors
- **Owner Notifications**: Critical errors sent to bot owner via DM

### Async Patterns
- **Database Context**: Always use context managers or decorators for DB operations
- **IPC Timeouts**: All IPC requests have configurable timeouts (default 5s)
- **Background Tasks**: Discord.py tasks for periodic operations
- **Connection Pooling**: Proper async connection management

### Type Safety
- **Type Hints**: Comprehensive type annotations throughout codebase
- **Custom Type Checking**: Advanced type validation system in `type_utils.py`
- **Generic Support**: Full generic type support with recursive validation
- **Runtime Validation**: Optional runtime type checking for critical paths

## Essential Files Reference

### Core Application
- `epsi_bot/__main__.py`: Application entry point with logging setup
- `epsi_bot/panel/app.py`: Panel class with process management and IPC
- `epsi_bot/bot/bot.py`: Bot class with cog loading and event handling

### Database & Models
- `epsi_bot/utils/models.py`: Complete ORM model definitions
- `epsi_bot/utils/ipc.py`: Custom IPC implementation with async support

### Audio & Caching
- `epsi_bot/utils/audio.py`: Audio processing and playback logic
- `epsi_bot/utils/cache.py`: Audio caching with compression and TTL

### Web Interface
- `epsi_bot/panel/routes/`: All web routes organized by functionality
- `epsi_bot/panel/templates/`: Jinja2 templates with responsive design
- `epsi_bot/panel/services/`: External service integrations (Discord API, cache)

### Configuration & Utilities
- `pyproject.toml`: Project metadata and dependencies
- `epsi_bot/utils/constants.py`: Application constants and error embeds
- `epsi_bot/utils/decorators.py`: Authentication and access control decorators

## Adding New Features

### Discord Commands
1. Create new cog in `epsi_bot/bot/cogs/` following existing patterns
2. Implement `setup(bot: Bot)` function for registration
3. Use `@commands.slash_command()` for new commands
4. Add error handling and user feedback via embeds

### Panel Routes
1. Create blueprint in `epsi_bot/panel/routes/`
2. Register in `routes/__init__.py`
3. Use appropriate decorators (`@login_required`, `@admin_required`)
4. Follow REST conventions and proper error handling

### Database Changes
1. Extend `BaseModel` for new models in `models.py`
2. Use Tortoise field types and relationships
3. Add proper indexes and constraints
4. Consider migration strategy for existing data

### IPC Extensions
1. Register handlers with `@bot.handle("channel_name")` in bot.py
2. Use `panel.get_from_bot("channel_name", **params)` from panel
3. Implement proper error handling and timeouts
4. Consider caching for frequently accessed data
