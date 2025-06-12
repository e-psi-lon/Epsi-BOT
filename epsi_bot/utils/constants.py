import re

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
	"OWNER_ID",
	"YOUTUBE_REGEX",
	"GET_FILE_HTTP_URL",
	"YOUTUBE_CLIENT"
]

OWNER_ID = 708006478807695450
EMBED_ERROR_QUEUE_EMPTY = discord.Embed(title="Error", description="The queue is empty.",
                                        color=discord.Color.dark_red())
EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST = discord.Embed(
	title="Error",
	description="A playlist with this name does not exist. Existing playlists:",
	color=discord.Color.dark_red()
)
EMBED_ERROR_BOT_NOT_CONNECTED = discord.Embed(
	title="Error",
	description="Bot is not connected to a voice channel.",
	color=discord.Color.dark_red()
)
EMBED_ERROR_BOT_NOT_PLAYING = discord.Embed(title="Error", description="Bot is not playing anything.",
                                            color=discord.Color.dark_red())
EMBED_ERROR_INDEX_TOO_HIGH = discord.Embed(title="Error", description="The index is too high.",
                                           color=discord.Color.dark_red())
EMBED_ERROR_NAME_TOO_LONG = discord.Embed(title="Error", description="The name is too long.",
                                          color=discord.Color.dark_red())
EMBED_ERROR_NO_RESULTS_FOUND = discord.Embed(title="Error", description="No results found.",
                                             color=discord.Color.dark_red())
EMBED_ERROR_VIDEO_TOO_LONG = discord.Embed(title="Error", description="The video is too long.",
                                           color=discord.Color.dark_red())
EMBED_ERROR_NOT_BOT_OWNER = discord.Embed(title="Error", description="You are not the owner of the bot.",
                                          color=discord.Color.dark_red())
YOUTUBE_REGEX = re.compile(
	r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/((watch\?v=)|(embed/)|(v/)|(.+\?v=))?([^&=%?]{11})')
GET_FILE_HTTP_URL = re.compile(r'^https?://[^\s/$.?#]+\.[^\s/]+/.*?([^/]+\.[^/\s?#]+)(?:\?.*)?(?:#.*)?$')

YOUTUBE_CLIENT = "WEB"
