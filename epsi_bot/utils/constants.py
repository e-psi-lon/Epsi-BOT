import re
from typing import Final

import discord

__all__ = [
	"EMBED_ERROR_QUEUE_EMPTY",
	"EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST",
	"EMBED_ERROR_BOT_NOT_CONNECTED",
	"EMBED_ERROR_BOT_NOT_PLAYING",
	"EMBED_ERROR_INDEX_TOO_HIGH",
	"EMBED_ERROR_NAME_TOO_LONG",
	"EMBED_ERROR_NO_RESULTS_FOUND",
	"EMBED_ERROR_VIDEO_TOO_LONG",
	"EMBED_ERROR_NOT_BOT_OWNER",
	"EMBED_ERROR_PLAYLIST_EXISTS",
	"OWNER_ID",
	"YOUTUBE_REGEX",
	"GET_FILE_HTTP_URL",
	"YOUTUBE_CLIENT",
	"MAX_TRACK_LENGTH"
]

OWNER_ID: Final[int] = 708006478807695450


def _embed_error(description: str) -> discord.Embed:
	"""
	Private function to create an embed reporting an error.
	"""
	return discord.Embed(title="Error", description=description, color=discord.Color.dark_red())


YOUTUBE_CLIENT: Final[str] = "WEB"

MAX_TRACK_LENGTH: Final[int] = 10_800  # in seconds, 10,800 seconds = 3 hours


EMBED_ERROR_QUEUE_EMPTY: Final[discord.Embed] = _embed_error("The queue is empty.")
EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST: Final[discord.Embed] = _embed_error("A playlist with this name does not exist. Existing playlists:")
EMBED_ERROR_BOT_NOT_CONNECTED: Final[discord.Embed] = _embed_error("The bot is not connected to a voice channel")
EMBED_ERROR_BOT_NOT_PLAYING: Final[discord.Embed] = _embed_error("The bot is not playing anything.")
EMBED_ERROR_INDEX_TOO_HIGH: Final[discord.Embed] = _embed_error("The index is too high.")
EMBED_ERROR_NAME_TOO_LONG: Final[discord.Embed] = _embed_error("The name is too long.")
EMBED_ERROR_NO_RESULTS_FOUND: Final[discord.Embed] = _embed_error("No results found.")
EMBED_ERROR_VIDEO_TOO_LONG: Final[discord.Embed] = _embed_error(f"The video is too long. A maximum length is {MAX_TRACK_LENGTH // 60} minutes.")
EMBED_ERROR_NOT_BOT_OWNER: Final[discord.Embed] = _embed_error("You are not the owner of the bot.")
EMBED_ERROR_PLAYLIST_EXISTS: Final[discord.Embed] = _embed_error("A playlist with this name already exists.")

YOUTUBE_REGEX: Final[re.Pattern] = re.compile(
	r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/((watch\?v=)|(embed/)|(v/)|(.+\?v=))?([^&=%?]{11})')
GET_FILE_HTTP_URL: Final[re.Pattern] = re.compile(r'^https?://[^\s/$.?#]+\.[^\s/]+/.*?([^/]+\.[^/\s?#]+)(?:\?.*)?(?:#.*)?$')

