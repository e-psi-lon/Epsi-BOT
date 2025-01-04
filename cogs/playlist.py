import asyncio

import discord
import pytubefix
from discord.commands import SlashCommandGroup
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError

from bot.bot import Bot
from utils import (Playlist,
                   Song,
                   Asker,
                   play_song,
                   get_playlists,
                   get_playlists_songs,
                   EMBED_ERROR_NAME_TOO_LONG,
                   EMBED_ERROR_QUEUE_EMPTY,
                   EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST,
                   EMBED_ERROR_BOT_NOT_CONNECTED,
                   Server,
                   get_user_playlists, PlaylistSong, ServerPlaylist, UserPlaylist,
                   )
from utils.utils import download_batch

class Playlists(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to playlists"

	playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

	create = playlist.create_subgroup(name="create", description="Creates a playlist")

	@create.command(name="from-queue", description="Creates a playlist from the queue")
	async def create_from_queue(self, ctx: discord.ApplicationContext,
								name: discord.Option(str, "The name of the playlist", required=True),  # type: ignore
								playlist_type: discord.Option(str, "The type of the playlist", required=False,
															  choices=["server", "user"],
															  default="server")):  # type: ignore
		await ctx.response.defer()
		if len(name) > 20:
			return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
		server = Server.get(server_id=ctx.interaction.guild.id)
		user_playlists = get_user_playlists(ctx.user.id)
		if not server.queue and not user_playlists:
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		if (name in [playlist.playlist.name for playlist in server.playlists] and playlist_type == "server") or \
			(name in [playlist.playlist.name for playlist in user_playlists] and playlist_type == "user"):
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
									color=discord.Color.dark_red()))
		playlist = Playlist.create(name=name)
		playlist.save()
		for queue_elem in server.queue:
			PlaylistSong.create(asker=queue_elem.asker, playlist=playlist, position=queue_elem.position, song=queue_elem.song).save()
		if playlist_type == "server":
			ServerPlaylist.create(playlist=playlist, server=server).save()
		else:
			UserPlaylist.create(playlist=playlist, user=Asker).save()
		await ctx.respond(
			embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=discord.Color.green()))

	@create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
	async def create_from_youtube(self, ctx: discord.ApplicationContext,
								  url: discord.Option(str, "The url of the playlist", required=True),  # type: ignore
								  name: discord.Option(str, "The name of the playlist", required=False),  # type: ignore
								  playlist_type: discord.Option(str, "The type of the playlist", required=False,
																choices=["server", "user"],
																default="server")):  # type: ignore
		await ctx.response.defer()
		server = Server.get(server_id=ctx.interaction.guild.id)
		user_playlists = get_user_playlists(ctx.user.id)
		try:
			playlist = pytubefix.Playlist(url)
			if name is None:
				name = playlist.title
			if len(name) > 20:
				return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
			if (name in [playlist.playlist.name for playlist in server.playlists] and playlist_type == "server") or \
					(name in [playlist.playlist.name for playlist in user_playlists] and playlist_type == "user"):
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
										color=discord.Color.dark_red()))
			db_playlist: Playlist = Playlist.create(name=name)
			for video in playlist.videos:
				song, _ = Song.get_or_create(name=video.title, url=video.watch_url)
				asker, _ = Asker.get_or_create(discord_id=ctx.user.id)
				PlaylistSong.create(asker=asker, playlist=db_playlist, song=song)
			if playlist_type == "server":
				ServerPlaylist.create(playlist=db_playlist, server=server)
			else:
				user, _ = Asker.get_or_create(discord_id=ctx.user.id)
				UserPlaylist.create(playlist=db_playlist, user=user)
			await ctx.respond(
				embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=discord.Color.green()))
		except PytubeRegexMatchError:
			await ctx.respond(
				embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist",
									color=discord.Color.dark_red()))

	@playlist.command(name="delete", description="Deletes a playlist")
	async def delete(self, ctx: discord.ApplicationContext,
					 name: discord.Option(str, "The name of the playlist", required=True,
										  autocomplete=discord.utils.basic_autocomplete(
											  get_playlists))):  # type: ignore
		user_playlists = get_user_playlists(ctx.user.id)
		server: Server = Server.get(server_id=ctx.guild.id)
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing server playlists:",
												value="\n".join(
													[playlist.playlist.name for playlist in server.playlists]))
									 .add_field(name="Existing user playlists:",
												value="\n".join([playlist.playlist.name for playlist in user_playlists])))
		if name not in [playlist.playlist.name for playlist in server.playlists]:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing playlists:",
												value="\n".join([playlist.playlist.name for playlist in server.playlists])))
		Playlist.delete().where(Playlist.name == name).execute()
		await ctx.respond(
			embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=discord.Color.green()))

	@playlist.command(name="add", description="Adds a song to a playlist")
	async def add(self, ctx: discord.ApplicationContext,
				  name: discord.Option(str, "The name of the playlist", required=True,
									   autocomplete=discord.utils.basic_autocomplete(get_playlists)),  # type: ignore
				  query: discord.Option(str, "The YouTube video to add to the playlist",
										required=True)):  # type: ignore
		await ctx.response.defer()
		user_playlists = get_user_playlists(ctx.user.id)
		server: Server = Server.get(server_id=ctx.guild.id)
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing server playlists:",
												value="\n".join(
													[playlist.playlist.name for playlist in server.playlists]))
									 .add_field(name="Existing user playlists:",
												value="\n".join([playlist.playlist.name for playlist in user_playlists])))
		try:
			url = pytubefix.YouTube(query).watch_url
			try:
				song, _ = Song.get_or_create(name=pytubefix.YouTube(query).title, url=url)
				playlist = Playlist.get(name=name)
				asker, _ = Asker.get_or_create(discord_id=ctx.user.id)
				PlaylistSong.create(asker=asker, playlist=playlist, song=song)
				await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song added to playlist {name}.",
													  color=discord.Color.green()))
			except IndexError:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="Error while getting song.", color=discord.Color.dark_red()))
		except PytubeRegexMatchError:
			return await ctx.respond(embed=discord.Embed(title="Error",
														 description="You must use an url of a youtube video "
																	 "(the research feature is not available for "
																	 "this command yet)",
														 color=discord.Color.dark_red()))

	@playlist.command(name="remove", description="Removes a song from a playlist")
	async def remove(self, ctx: discord.ApplicationContext,
					 name: discord.Option(str, "The name of the playlist", required=True,
										  autocomplete=discord.utils.basic_autocomplete(get_playlists)),  # type: ignore
					 song: discord.Option(str, "The name of the song", required=True,
										  autocomplete=discord.utils.basic_autocomplete(
											  get_playlists_songs))): # type: ignore
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing server playlists:",
												value="\n".join(
													[playlist.playlist.name for playlist in Server.get(server_id=ctx.guild.id).playlists]))
									 .add_field(name="Existing user playlists:",
												value="\n".join([playlist.playlist.name for playlist in get_user_playlists(ctx.user.id)])))
		song: Song | None = Song.get_or_none(name=song)
		if song is None:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=discord.Color.dark_red()))
		playlist = Playlist.get(name=name)
		playlist_song = PlaylistSong.get(playlist=playlist, song=song)
		playlist_song.delete().execute()
		await ctx.respond(
			embed=discord.Embed(title="Playlist", description=f"Song {song.name} removed from playlist {name}.",
								color=discord.Color.green()))

	@playlist.command(name="play", description="Plays a playlist")
	async def play(self, ctx: discord.ApplicationContext,
				   name: discord.Option(str, "The name of the playlist", required=True,
										autocomplete=discord.utils.basic_autocomplete(get_playlists))):  # type: ignore
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		server: Server = Server.get(server_id=ctx.guild.id)
		user_playlist = get_user_playlists(ctx.user.id)
		playlist: Playlist
		if name.endswith(" - SERVER") and name[:-9] in [playlists.playlist.name for playlists in server.playlists]:
			playlist = Playlist.get(name=name[:-9])
		elif name.endswith(" - USER") and name[:-7] in [playlists.playlist.name for playlists in user_playlist]:
			playlist = Playlist.get(name=name[:-7])
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing server playlists:",
												value="\n- ".join([playlists.playlist.name for playlists in server.playlists]))
									 .add_field(name="Existing user playlists:",
												value="\n- ".join(
													[playlists.playlist.name for playlists in user_playlist])))
		if not playlist:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing server playlists:",
												value="\n- ".join([playlists.playlist.name for playlists in server.playlists]))
									 .add_field(name="Existing user playlists:",
												value="\n- ".join(
													[playlists.playlist.name for playlists in user_playlist])))

		server.queue = [{"name": song.song.name, "url": song.song.url, "asker": song.asker.discord_id} for song in playlist.songs]
		server.position = 0
		server.save()
		await play_song(ctx, server.queue[0].song.url)
		await ctx.respond(
			embed=discord.Embed(title="Play", description=f"Playing {server.queue[server.position].song.name}",
								color=discord.Color.green()))
		futures: list[asyncio.Future] = []
		if len(server.queue) > 1:
			queue = [queue.song.url for queue in server.queue[1:]]
			await download_batch(queue)

	@playlist.command(name="list", description="Lists all the playlists")
	async def list_playlist(self, ctx: discord.ApplicationContext,
							playlist_type: discord.Option(str, "The type of the playlist", required=False,
														  choices=["server", "user"],
														  default="server")):  # type: ignore
		await ctx.response.defer()
		playlists: list[ServerPlaylist | UserPlaylist] = Server.get(server_id=ctx.guild.id).playlists if playlist_type == "server" else get_user_playlists(ctx.user.id)
		if not playlists:
			return await ctx.respond(
				embed=discord.Embed(title="Playlists", description="No playlists.", color=discord.Color.green()))
		embed = discord.Embed(title="Playlists", color=discord.Color.green())
		for index, name in enumerate([playlist.playlist.name for playlist in playlists][:24]):
			embed.add_field(name=f"__{name}__ :",
							value=f"{len([playlist for playlist in playlists][index].playlist.songs)} song"
								f"{'s' if len([playlist for playlist in playlists][index].playlist.songs) > 1 else ''}")
			if index == 23 and len([playlist for playlist in playlists]) > 24:
				embed.add_field(name="And more...", value="")
				break
		await ctx.respond(embed=embed)

	@playlist.command(name="show", description="Shows a playlist")
	async def show(self, ctx: discord.ApplicationContext,
				   name: discord.Option(str, "The name of the playlist", required=True,
										autocomplete=discord.utils.basic_autocomplete(get_playlists))):  # type: ignore
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:",
												value="\n- ".join([playlist.playlist.name for playlist in Server.get(server_id=ctx.guild.id).playlists]))
			                         .add_field(name="Existing user playlists:",
			                                    value="\n- ".join([playlist.playlist.name for playlist in get_user_playlists(ctx.user.id)])))
		embed = discord.Embed(title=name, color=discord.Color.green())
		playlist_songs: list[PlaylistSong] = Playlist.get(name=name).songs
		for index, playlist_song in enumerate(playlist_songs):
			song: Song = playlist_song.song
			embed.add_field(name=f"{index + 1}.", value=f"__[{song.name}]({song.url})__")
			if index == 23 and len(playlist_songs) > 24:
				embed.add_field(name="...", value="")
				break
		await ctx.respond(embed=embed)

	@playlist.command(name="rename", description="Renames a playlist")
	async def rename(self, ctx: discord.ApplicationContext,
					 name: discord.Option(str, "The name of the playlist", required=True,
										  autocomplete=discord.utils.basic_autocomplete(get_playlists)),  # type: ignore
					 new_name: discord.Option(str, "The new name of the playlist", required=True)):  # type: ignore
		await ctx.response.defer()
		if len(new_name) > 20:
			return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
		config, name = await self.get_config(ctx, name)
		if config is None:
			return
		if name not in [playlist.name for playlist in config.playlists]:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
									 .add_field(name="Existing playlists:",
												value="\n".join([playlist.name for playlist in config.playlists])))
		if new_name in [playlist.name for playlist in config.playlists]:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
									color=discord.Color.dark_red()))
		playlist: Playlist = Playlist.get(name=name)
		playlist.name = new_name
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.",
											  color=discord.Color.green()))

	@playlist.command(name="copy", description="Copies a playlist to another playlist type")
	async def copy(self, ctx: discord.ApplicationContext,
					 name: discord.Option(str, "The name of the playlist", required=True,
										 autocomplete=discord.utils.basic_autocomplete(get_playlists)),  # type: ignore
					):
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
			                         .add_field(name="Existing server playlists:",
												value="\n- ".join([playlist.playlist.name for playlist in Server.get(server_id=ctx.guild.id).playlists]))
			                         .add_field(name="Existing user playlists:",
			                                    value="\n- ".join([playlist.playlist.name for playlist in get_user_playlists(ctx.user.id)])))
		playlist = Playlist.get(name=name)
		if playlist is not None:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
									color=discord.Color.dark_red()))
		# Si la playlist est une playlist utilisateur
		if playlist in get_user_playlists(ctx.user.id):
			new_playlist = Playlist.create(name=name)
			new_playlist.save()
			for song in Playlist.get(name=name).songs:
				PlaylistSong.create(asker=song.asker, playlist=new_playlist, position=song.position, song=song.song)
			UserPlaylist.create(playlist=new_playlist, user=Asker.get_or_create(discord_id=ctx.user.id)[0]).save()
		else:
			new_playlist = Playlist.create(name=name)
			new_playlist.save()
			for song in Playlist.get(name=name).songs:
				PlaylistSong.create(asker=song.asker, playlist=new_playlist, position=song.position, song=song.song)
			ServerPlaylist.create(playlist=new_playlist, server=Server.get(server_id=ctx.guild.id)).save()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} copied.",
												color=discord.Color.green()))


def setup(bot):
	bot.add_cog(Playlists(bot))
