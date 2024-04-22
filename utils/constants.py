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
    "OWNER_ID"
]

OWNER_ID = 708006478807695450
EMBED_ERROR_QUEUE_EMPTY = discord.Embed(title="Error", description="The queue is empty.", color=0xff0000)
EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST = discord.Embed(title="Error", description="A playlist with this name does "
                                                                                  "not exist. Existing playlists:",
                                                       color=0xff0000)
EMBED_ERROR_BOT_NOT_CONNECTED = discord.Embed(title="Error", description="Bot is not connected to a voice channel.",
                                              color=0xff0000)
EMBED_ERROR_BOT_NOT_PLAYING = discord.Embed(title="Error", description="Bot is not playing anything.", color=0xff0000)
EMBED_ERROR_INDEX_TOO_HIGH = discord.Embed(title="Error", description="The index is too high.", color=0xff0000)
EMBED_ERROR_NAME_TOO_LONG = discord.Embed(title="Error", description="The name is too long.", color=0xff0000)
EMBED_ERROR_NO_RESULTS_FOUND = discord.Embed(title="Error", description="No results found.", color=0xff0000)
EMBED_ERROR_VIDEO_TOO_LONG = discord.Embed(title="Error", description="The video is too long.", color=0xff0000)
