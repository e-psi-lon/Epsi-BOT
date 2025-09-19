import asyncio
from enum import Enum
from typing import Optional, cast
import discord
import pytubefix  # type: ignore[import-untyped]
from discord.commands import SlashCommandGroup
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError  # type: ignore[import-untyped]

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import (Playlist,
                            Song,
                            User,
                            play_song,
                            get_playlists,
                            get_playlists_songs,
                            EMBED_ERROR_QUEUE_EMPTY,
                            EMBED_ERROR_BOT_NOT_CONNECTED,
                            EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST,
							EMBED_ERROR_NAME_TOO_LONG,
							EMBED_ERROR_PLAYLIST_EXISTS,
                            Server, PlaylistReference, PlaylistSong, ServerPlaylist, UserPlaylist, Queue,
                            download_bulk,
                            get_youtube,
							YOUTUBE_CLIENT
                            )

class PlaylistType(Enum):
	"""
	Enum for playlist types to ensure type safety.
	
	Attributes
	----------
	SERVER : str
		Server-level playlist type
	USER : str
		User-level playlist type
	"""
	SERVER = "server"
	USER = "user"



class Playlists(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to playlists"

	playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")
	create = playlist.create_subgroup(name="create", description="Creates a playlist")

	# ==================== PLAYLIST CREATION COMMANDS ====================
	
	@create.command(name="from-queue", description="Creates a playlist from the queue")
	@discord.option("name", str, description="The name of the playlist", required=True)
	@discord.option("playlist-type", str, description="The type of the playlist", required=False,
	                choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4,
	                max_length=6)
	async def create_from_queue(self, ctx: discord.ApplicationContext, name: str, playlist_type: str) -> None:
		await ctx.response.defer()
		if ctx.interaction.guild is None:
			await ctx.respond(embed=discord.Embed(title="Error", description="This command can only be used in a server."))
			return
		clean_name, parsed_type, error = validate_and_parse_playlist(name, playlist_type)
		if error:
			await ctx.respond(embed=error)
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		server, user, user_playlists = await get_common_data(ctx)
		queue_songs = await server.queue.all()
		if not queue_songs:
			await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
			return
		if check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_EXISTS)
			return
		playlist = await Playlist.create(name=clean_name)
		
		playlist_songs_to_create = [
			PlaylistSong(
				asker=queue_elem.asker, 
				playlist=playlist, 
				position=queue_elem.position, 
				song=queue_elem.song
			) for queue_elem in queue_songs
		]
		await PlaylistSong.bulk_create(playlist_songs_to_create)
		
		if parsed_type == PlaylistType.SERVER:
			await ServerPlaylist.create(playlist=playlist, server=server)
		else:
			await UserPlaylist.create(playlist=playlist, user=user)
			
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {clean_name} created.", color=discord.Color.green()))

	@create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
	@discord.option("url", str, description="The url of the playlist", required=True)
	@discord.option("name", str, description="The name of the playlist", required=False)
	@discord.option("playlist-type", str, description="The type of the playlist", required=False,
	                choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4,
	                max_length=6)
	async def create_from_youtube(self, ctx: discord.ApplicationContext, url: str, name: str, playlist_type: str) -> None:
		await ctx.response.defer()
		try:
			if ctx.interaction.guild is None:
				await ctx.respond(embed=discord.Embed(title="Error", description="This command can only be used in a server."))
				return
			
			playlist = pytubefix.Playlist(url, client=YOUTUBE_CLIENT)
			if name is None:
				name = playlist.title
			
			# Validate and parse
			clean_name, parsed_type, error = validate_and_parse_playlist(name, playlist_type)
			if error:
				await ctx.respond(embed=error)
				return
			else:
				clean_name = cast(str, clean_name)
				parsed_type = cast(PlaylistType, parsed_type)

			# Get data
			server, user, user_playlists = await get_common_data(ctx)
			
			# Check existence
			if check_playlist_exists(clean_name, parsed_type, server, user_playlists):
				await ctx.respond(embed=EMBED_ERROR_PLAYLIST_EXISTS)
				return
				
			db_playlist = await Playlist.create(name=clean_name)
			
			# Create songs and playlist entries using bulk creation
			songs_to_create = []
			for idx, video in enumerate(playlist.videos):
				song, _ = await Song.get_or_create(name=video.title, url=video.watch_url)
				songs_to_create.append(PlaylistSong(
					asker=user, 
					playlist=db_playlist, 
					song=song,
					position=idx + 1
				))
			
			await PlaylistSong.bulk_create(songs_to_create)
			
			if parsed_type == PlaylistType.SERVER:
				await ServerPlaylist.create(playlist=db_playlist, server=server)
			else:
				await UserPlaylist.create(playlist=db_playlist, user=user)
				
			await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {clean_name} created.", color=discord.Color.green()))
		except PytubeRegexMatchError:
			await ctx.respond(
				embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist",
				                    color=discord.Color.dark_red()))

	# ==================== PLAYLIST MANAGEMENT COMMANDS ====================

	@playlist.command(name="delete", description="Deletes a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def delete(self, ctx: discord.ApplicationContext, name: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		server, user, user_playlists = await get_common_data(ctx)
		if error is None and parsed_type is None:
			# Show available playlists
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:",
			                                    value="\n".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:",
			                                    value="\n".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)

		# Check if playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = [p.playlist.name for p in server.playlists] if parsed_type == PlaylistType.SERVER else [p.playlist.name for p in user_playlists]
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:",
			                                    value="\n".join(playlist_names)))
			return
										 

		playlist_to_del: PlaylistReference
		if parsed_type == PlaylistType.SERVER:
			playlist_to_del = await ServerPlaylist.filter(playlist__name=clean_name, server=server).get()
		else:
			playlist_to_del = await UserPlaylist.filter(playlist__name=clean_name, user=user).get()
		playlist_id = (await playlist_to_del.playlist.get()).playlist_id
		await playlist_to_del.playlist.delete()
		songs_to_delete = await PlaylistSong.filter(playlist_id=playlist_id).all()
		await asyncio.gather(*(song.delete() for song in songs_to_delete))
		await playlist_to_del.delete()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {clean_name} deleted.", color=discord.Color.green()))

	@playlist.command(name="add", description="Adds a song to a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("query", str, description="The YouTube video to add to the playlist", required=True)
	async def add(self, ctx: discord.ApplicationContext, name: str, query: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		server, user, user_playlists = await get_common_data(ctx)
		if error is None and parsed_type is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		# Check if playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = [p.playlist.name for p in server.playlists] if parsed_type == PlaylistType.SERVER else [p.playlist.name for p in user_playlists]
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:", value="\n".join(playlist_names)))
			return
		
		try:
			url = get_youtube(query).watch_url
			song, _ = await Song.get_or_create(name=get_youtube(query).title, url=url)
			playlist = await Playlist.get(name=clean_name)
			await PlaylistSong.create(asker=user, playlist=playlist, song=song)
			await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song added to playlist {clean_name}.", color=discord.Color.green()))
		except IndexError:
			await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting song.", color=discord.Color.dark_red()))
		except PytubeRegexMatchError:
			await ctx.respond(embed=discord.Embed(title="Error", description="You must use an url of a youtube video (the research feature is not available for this command yet)", color=discord.Color.dark_red()))

	@playlist.command(name="remove", description="Removes a song from a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("song", str, description="The name of the song", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))
	async def remove(self, ctx: discord.ApplicationContext, name: str, song: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		server, _, user_playlists = await get_common_data(ctx)
		if error is None and parsed_type is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		# Check if playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = [p.playlist.name for p in server.playlists] if parsed_type == PlaylistType.SERVER else [p.playlist.name for p in user_playlists]
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:", value="\n".join(playlist_names)))
			return
		
		song_to_remove = await Song.get_or_none(name=song)
		if song_to_remove is None:
			await ctx.respond(embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=discord.Color.dark_red()))
			return
		playlist = await Playlist.get(name=clean_name)
		playlist_song = await PlaylistSong.get_or_none(playlist=playlist, song=song_to_remove)
		if playlist_song is None:
			await ctx.respond(embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=discord.Color.dark_red()))
			return
		await playlist_song.delete()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song {song_to_remove.name} removed from playlist {clean_name}.", color=discord.Color.green()))

	# ==================== PLAYLIST PLAYBACK COMMANDS ====================

	@playlist.command(name="play", description="Plays a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def play(self, ctx: discord.ApplicationContext, name: str) -> None:
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		
		# Use get_common_data for consistent error handling
		server, _, user_playlists = await get_common_data(ctx)
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		if error is None and parsed_type is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n- ".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n- ".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		# Check if playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = [p.playlist.name for p in server.playlists] if parsed_type == PlaylistType.SERVER else [p.playlist.name for p in user_playlists]
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:", value="\n- ".join(playlist_names)))
			return
		
		playlist = await Playlist.get(name=clean_name)

		await server.queue.all().delete()
		songs = await playlist.songs.all().prefetch_related("song", "asker")
		songs_creation = [
			Queue(asker=x.asker, server=server, song=x.song, position=x.position) 
			for x in songs
		]
		await Queue.bulk_create(songs_creation)

		server.position = 0
		await server.save()
		
		# Refresh the queue data after bulk creation
		await server.fetch_related("queue", "queue__song")
		url = server.queue[0].song.url
		try:
			url = get_youtube(url).streams.get_audio_only().url
		except PytubeRegexMatchError:
			pass
		await play_song(ctx, url, direct_play=True)
		await ctx.respond(
			embed=discord.Embed(title="Play", description=f"Playing {server.queue[server.position].song.name}",
			                    color=discord.Color.green()))
		queue = [queue.song.url for queue in server.queue]
		asyncio.create_task(download_bulk(queue))

	# ==================== PLAYLIST VIEW/INFO COMMANDS ====================

	@playlist.command(name="list", description="Lists all the playlists")
	@discord.option("playlist-type", str, description="The type of the playlist", required=False,
	                choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4,
	                max_length=6)
	async def list_playlist(self, ctx: discord.ApplicationContext, playlist_type: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist type
		_, parsed_type, error = validate_and_parse_playlist("dummy", playlist_type)
		if error:
			await ctx.respond(embed=error)
			return
		
		# Use get_common_data for consistent error handling
		server, _, user_playlists = await get_common_data(ctx)

		playlists = await server.playlists.all() if parsed_type == PlaylistType.SERVER else user_playlists

		if not playlists:
			await ctx.respond(embed=discord.Embed(title="Playlists", description="No playlists.", color=discord.Color.green()))
			return
			
		embed = discord.Embed(title="Playlists", color=discord.Color.green())
		for index, playlist in enumerate(playlists[:24]):
			song_count = await playlist.playlist.songs.all().count()
			embed.add_field(name=f"__{playlist.playlist.name}__ :", value=f"{song_count} song{'s' if song_count != 1 else ''}")
			if index == 23 and len(playlists) > 24:
				embed.add_field(name="And more...", value="")
				break
		await ctx.respond(embed=embed)

	@playlist.command(name="show", description="Shows a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def show(self, ctx: discord.ApplicationContext, name: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		server, _, user_playlists = await get_common_data(ctx)
		if error is None and parsed_type is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n- ".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n- ".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		# Check if playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = [p.playlist.name for p in server.playlists] if parsed_type == PlaylistType.SERVER else [p.playlist.name for p in user_playlists]
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:", value="\n- ".join(playlist_names)))
			return
		
		embed = discord.Embed(title=clean_name, color=discord.Color.green())
		playlist_songs = await (await Playlist.get(name=clean_name)).songs.all().prefetch_related("song")
		for index, playlist_song in enumerate(playlist_songs[:24]):
			song = playlist_song.song
			embed.add_field(name=f"{index + 1}.", value=f"__[{song.name}]({song.url})__")
			if index == 23 and len(playlist_songs) > 24:
				embed.add_field(name="...", value="")
				break
		await ctx.respond(embed=embed)

	@playlist.command(name="rename", description="Renames a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("new-name", str, description="The new name of the playlist", required=True,
	                parameter_name="new_name")
	async def rename(self, ctx: discord.ApplicationContext, name: str, new_name: str) -> None:
		await ctx.response.defer()
		
		# Validate new name and parse current name
		name_error = validate_playlist_name(new_name)
		if name_error:
			await ctx.respond(embed=name_error)
			return
		
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		server, _, user_playlists = await get_common_data(ctx)
		if error is None and parsed_type is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n- ".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n- ".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		server_playlists_names = [p.playlist.name for p in server.playlists]
		user_playlists_names = [p.playlist.name for p in user_playlists]
		
		# Check if the playlist exists in the correct type
		if not check_playlist_exists(clean_name, parsed_type, server, user_playlists):
			playlist_names = server_playlists_names if parsed_type == PlaylistType.SERVER else user_playlists_names
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name=f"Existing {parsed_type.value} playlists:", value="\n".join(playlist_names)))
			return
			
		if new_name in server_playlists_names + user_playlists_names:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_EXISTS)
			return
		
		playlist = await Playlist.get(name=clean_name)
		playlist.name = new_name
		await playlist.save()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {clean_name} renamed to {new_name}.", color=discord.Color.green()))

	@playlist.command(name="copy", description="Copies a playlist to the other playlist type")
	@discord.option("name", str, description="The name of the playlist", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def copy(self, ctx: discord.ApplicationContext, name: str) -> None:
		await ctx.response.defer()
		
		# Parse playlist name and type
		clean_name, parsed_type, error = validate_and_parse_playlist(name)
		if error is None and parsed_type is None:
			server, _, user_playlists = await get_common_data(ctx)
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:", value="\n- ".join([p.playlist.name for p in server.playlists]))
			                         .add_field(name="Existing user playlists:", value="\n- ".join([p.playlist.name for p in user_playlists])))
			return
		else:
			clean_name = cast(str, clean_name)
			parsed_type = cast(PlaylistType, parsed_type)
		
		source_playlist = await Playlist.get_or_none(name=clean_name)
		if source_playlist is None:
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST)
			return
		
		server, user, user_playlists = await get_common_data(ctx)
		
		# Determine target type (opposite of source)
		target_type = PlaylistType.USER if parsed_type == PlaylistType.SERVER else PlaylistType.SERVER
		
		# Check if playlist already exists in target type
		if check_playlist_exists(clean_name, target_type, server, user_playlists):
			await ctx.respond(embed=EMBED_ERROR_PLAYLIST_EXISTS)
			return
		
		# Create new playlist and copy songs
		new_playlist = await Playlist.create(name=clean_name)
		source_songs = await source_playlist.songs.all().prefetch_related("song", "asker")
		
		# Create playlist songs for the new playlist using bulk creation
		playlist_songs_to_create = [
			PlaylistSong(
				asker=source_song.asker, 
				playlist=new_playlist, 
				song=source_song.song,
				position=source_song.position
			) for source_song in source_songs
		]
		await PlaylistSong.bulk_create(playlist_songs_to_create)
		
		# Link to appropriate type
		if target_type == PlaylistType.SERVER:
			await ServerPlaylist.create(playlist=new_playlist, server=server)
		else:
			await UserPlaylist.create(playlist=new_playlist, user=user)
			
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {clean_name} copied.", color=discord.Color.green()))


# ==================== UTILITY FUNCTIONS ====================

async def get_common_data(ctx: discord.ApplicationContext) -> tuple[Server, User, list[UserPlaylist]]:
	"""
	Retrieves common data needed for playlist operations.
	
	Parameters
	----------
	ctx : discord.ApplicationContext
		The Discord application context containing guild and user information
	
	Returns
	-------
	tuple[Server, User, list[UserPlaylist]]
		A tuple containing the server, user, and user playlists
		
	Raises
	------
	ValueError
		If the command is not used in a server or if the server is not found in database
	"""
	if ctx.guild is None:
		raise ValueError("This command can only be used in a server.")
	
	server = await Server.get_or_none(server_id=ctx.guild.id)
	if server is None:
		raise ValueError("Server not found in database. Bot may need to be reinitialized for this server.")
	
	await server.fetch_related("playlists", "playlists__playlist")
	user, _ = await User.get_or_create(discord_id=ctx.user.id)
	user_playlists = await user.playlists.all().prefetch_related("playlist")
	return server, user, user_playlists

def validate_and_parse_playlist(name: str, playlist_type: Optional[str] = None) -> tuple[Optional[str], Optional[PlaylistType], Optional[discord.Embed]]:
	"""
	Validate and parse playlist name and type.
	
	Parameters
	----------
	name : str
		The playlist name to validate and parse
	playlist_type : Optional[str], optional
		The playlist type string, by default None
		
	Returns
	-------
	tuple[Optional[str], Optional[PlaylistType], Optional[discord.Embed]]
		A tuple containing clean name, parsed type, and error embed (if any)
	"""
	if playlist_type:
		name_error = validate_playlist_name(name)
		if name_error:
			return None, None, name_error
		parsed_type = parse_playlist_name_and_type(playlist_type)[1]
		if not parsed_type:
			return None, None, discord.Embed(title="Error", description="Invalid playlist type. Use 'server' or 'user'.")
		return name, parsed_type, None
	else:
		clean_name, parsed_type = parse_playlist_name_and_type(name)
		if not parsed_type:
			return None, None, None
		return clean_name, parsed_type, None

def check_playlist_exists(name: str, playlist_type: PlaylistType, server: Server, user_playlists: list[UserPlaylist]) -> bool:
	"""
	Check if playlist exists for given type.
	
	Parameters
	----------
	name : str
		The name of the playlist to check
	playlist_type : PlaylistType
		The type of playlist (SERVER or USER)
	server : Server
		The server object containing server playlists
	user_playlists : list[UserPlaylist]
		List of user playlists
		
	Returns
	-------
	bool
		True if playlist exists, False otherwise
	"""
	if playlist_type == PlaylistType.SERVER:
		return name in [p.playlist.name for p in server.playlists]
	else:
		return name in [p.playlist.name for p in user_playlists]



def validate_playlist_name(name: str) -> Optional[discord.Embed]:
	"""
	Validate playlist name length.
	
	Parameters
	----------
	name : str
		The playlist name to validate
		
	Returns
	-------
	Optional[discord.Embed]
		Error embed if invalid, None if valid
	"""
	if len(name) > 20:
		return EMBED_ERROR_NAME_TOO_LONG
	return None


def parse_playlist_name_and_type(name: str) -> tuple[str, Optional[PlaylistType]]:
	"""
	Parse playlist name and extract type suffix if present.
	
	Parameters
	----------
	name : str
		The playlist name to parse
		
	Returns
	-------
	tuple[str, Optional[PlaylistType]]
		A tuple containing the clean name and playlist type (if found)
	"""
	if name.endswith(" - SERVER"):
		return name[:-9], PlaylistType.SERVER
	elif name.endswith(" - USER"):
		return name[:-7], PlaylistType.USER
	else:
		return name, None



def setup(bot: Bot) -> None:
	bot.add_cog(Playlists(bot))
