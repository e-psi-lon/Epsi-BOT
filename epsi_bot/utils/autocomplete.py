import discord

from epsi_bot.utils.models import Asker, Server, database_context

__all__ = ["get_playlists", "get_playlists_songs", "get_queue_songs"]


async def get_playlists(ctx: discord.AutocompleteContext) -> list[str]:
	"""
	Discord autocomplete function to get the playlists of the server and the user 
	typing the command.
	
	Parameters
	----------
	ctx : discord.AutocompleteContext
		The context of the command
	
	Returns
	-------
	list[str]
		The list of playlists
	"""
	async with database_context():
		config = await Server.get(server_id=ctx.interaction.guild.id).prefetch_related("playlists",
		                                                                               "playlists__playlist")
		user = await Asker.get(discord_id=ctx.interaction.user.id).prefetch_related("playlists", "playlists__playlist")
		return ([playlist.playlist.name + " - SERVER" for playlist in config.playlists] +
		        [playlist.playlist.name + " - USER" for playlist in user.playlists])


async def get_playlists_songs(ctx: discord.AutocompleteContext) -> list[str]:
	"""
	Discord autocomplete function to get the songs of a playlist which name is
	given as an argument to the command.

	Parameters
	----------
	ctx : discord.AutocompleteContext
		The context of the command

	Returns
	-------
	list[str]
		The list of songs in the playlist
	"""
	async with database_context():
		if ctx.options['playlist'].endswith(" - SERVER"):
			server = await Server.get(server_id=ctx.interaction.guild.id).prefetch_related("playlists",
			                                                                               "playlists__playlist",
			                                                                               "playlists__playlist__songs")
			for server_playlist in server.playlists:
				playlist = server_playlist.playlist
				if playlist.name == ctx.options['playlist'][:-9]:
					return [song.song.name for song in playlist.songs]
		elif ctx.options['playlist'].endswith(" - USER"):
			user = await Asker.get(discord_id=ctx.interaction.user.id).prefetch_related("playlists",
			                                                                            "playlists__playlist",
			                                                                            "playlists__playlist__songs")
			for user_playlist in user.playlists:
				if user_playlist.playlist.name == ctx.options['playlist'][:-7]:
					return [song.song.name for song in user_playlist.playlist.songs]
		else:
			return []


async def get_queue_songs(ctx: discord.AutocompleteContext) -> list[str]:
	"""
	Discord autocomplete function to get the songs in the queue.
	
	Parameters
	----------
	ctx : discord.AutocompleteContext
		The context of the command
		
	Returns
	-------
	list[str]
		The list of songs in the queue
	"""
	async with database_context():
		config = await Server.get(server_id=ctx.interaction.guild.id).prefetch_related("queue", "queue__song")
		if len(config.queue) < 1:
			return []
		queue = await config.queue.all()
		await queue.pop(config.position)
		queue_songs = list(map(lambda queue_elem: queue_elem.song, queue))
		return [song.name for song in queue_songs]
