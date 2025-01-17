import discord
import pytubefix
from discord.commands import SlashCommandGroup
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError

from epsi_bot.utils.models import Queue, database_context

from ..bot.bot import Bot
from ..utils import (Playlist,
				   Song,
				   Asker,
				   play_song,
				   get_playlists,
				   get_playlists_songs,
				   EMBED_ERROR_NAME_TOO_LONG,
				   EMBED_ERROR_QUEUE_EMPTY,
				   EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST,
				   EMBED_ERROR_BOT_NOT_CONNECTED,
				   Server, PlaylistSong, ServerPlaylist, UserPlaylist,
				   download_batch
				   )


class Playlists(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to playlists"

	playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

	create = playlist.create_subgroup(name="create", description="Creates a playlist")

	@create.command(name="from-queue", description="Creates a playlist from the queue")
	@discord.option("name", str, description="The name of the playlist", required=True)
	@discord.option("playlist-type", str, description="The type of the playlist", required=False, choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4, max_length=6)
	async def create_from_queue(self, ctx: discord.ApplicationContext, name: str, playlist_type: str):
		await ctx.response.defer()
		if len(name) > 20:
			return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
		async with database_context():
			server = await Server.get(server_id=ctx.interaction.guild.id)
			user_playlists = await (await Asker.get(discord_id=ctx.user.id)).playlists.all()
			if not await server.queue.all() and not user_playlists:
				return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
			if (name in [playlist.playlist.name for playlist in server.playlists] and playlist_type == "server") or \
				(name in [playlist.playlist.name for playlist in user_playlists] and playlist_type == "user"):
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
										color=discord.Color.dark_red()))
			playlist = await Playlist.create(name=name)
			for queue_elem in server.queue:
				await PlaylistSong.create(asker=queue_elem.asker, playlist=playlist, position=queue_elem.position, song=queue_elem.song).save()
			if playlist_type == "server":
				await ServerPlaylist.create(playlist=playlist, server=server).save()
			else:
				await UserPlaylist.create(playlist=playlist, user=Asker).save()
			await ctx.respond(
				embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=discord.Color.green()))

	@create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
	@discord.option("url", str, description="The url of the playlist", required=True)
	@discord.option("name", str, description="The name of the playlist", required=False)
	@discord.option("playlist-type", str, description="The type of the playlist", required=False, choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4, max_length=6)
	async def create_from_youtube(self, ctx: discord.ApplicationContext, url: str, name: str, playlist_type: str):
		await ctx.response.defer()
		try:
			async with database_context():
				server = await Server.get(server_id=ctx.interaction.guild.id)
				user_playlists = (await Asker.get(ctx.user.id)).playlists
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
				db_playlist = await Playlist.create(name=name)
				for video in playlist.videos:
					song, _ = await Song.get_or_create(name=video.title, url=video.watch_url)
					asker, _ = await Asker.get_or_create(discord_id=ctx.user.id)
					await PlaylistSong.create(asker=asker, playlist=db_playlist, song=song)
				if playlist_type == "server":
					await ServerPlaylist.create(playlist=db_playlist, server=server)
				else:
					user, _ = await Asker.get_or_create(discord_id=ctx.user.id)
					await UserPlaylist.create(playlist=db_playlist, user=user)
				await ctx.respond(
					embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=discord.Color.green()))
		except PytubeRegexMatchError:
			await ctx.respond(
				embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist",
									color=discord.Color.dark_red()))

	@playlist.command(name="delete", description="Deletes a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))	
	async def delete(self, ctx: discord.ApplicationContext, name: str):
		async with database_context():
			user_playlists = (await Asker.get(discord_id=ctx.user.id)).playlists
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
			await Playlist.filter(name=name).delete()
			await ctx.respond(
				embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=discord.Color.green()))

	@playlist.command(name="add", description="Adds a song to a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("query", str, description="The YouTube video to add to the playlist", required=True)
	async def add(self, ctx: discord.ApplicationContext, name: str, query: str):
		await ctx.response.defer()
		async with database_context():
			user_playlists = await (await Asker.get(ctx.user.id)).playlists.all()
			server = await Server.get(server_id=ctx.guild.id)
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
					song, _ = await Song.get_or_create(name=pytubefix.YouTube(query).title, url=url)
					playlist = await Playlist.get(name=name)
					asker, _ = await Asker.get_or_create(discord_id=ctx.user.id)
					await PlaylistSong.create(asker=asker, playlist=playlist, song=song)
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
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("song", str, description="The name of the song", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))
	async def remove(self, ctx: discord.ApplicationContext, name: str, song: str):
		await ctx.response.defer()
		async with database_context():
			if name.endswith(" - SERVER"):
				name = name[:-9]
			elif name.endswith(" - USER"):
				name = name[:-7]
			else:
				server = await Server.get(server_id=ctx.guild.id)
				user_playlists = await (await Asker.get(discord_id=ctx.user.id)).playlists.all()
				return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
										.add_field(name="Existing server playlists:",
													value="\n".join(
														[playlist.playlist.name for playlist in server.playlists]))
										.add_field(name="Existing user playlists:",
													value="\n".join([playlist.playlist.name for playlist in user_playlists])))
			song_to_remove = await Song.get_or_none(name=song)
			if song_to_remove is None:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=discord.Color.dark_red()))
			playlist = await Playlist.get(name=name)
			playlist_song = await PlaylistSong.get(playlist=playlist, song=song_to_remove)
			await playlist_song.delete()
			await ctx.respond(
				embed=discord.Embed(title="Playlist", description=f"Song {song_to_remove.name} removed from playlist {name}.",
									color=discord.Color.green()))

	@playlist.command(name="play", description="Plays a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def play(self, ctx: discord.ApplicationContext, name: str):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		async with database_context():
			server = await Server.get(server_id=ctx.guild.id)
			user_playlist = await (await Asker.get(discord_id=ctx.user.id)).playlists.all()
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

			await server.queue.all().delete()
			await Queue.bulk_create(await playlist.songs.all())

			server.position = 0
			await server.save()
			await play_song(ctx, server.queue[0].song.url)
			await ctx.respond(
				embed=discord.Embed(title="Play", description=f"Playing {server.queue[server.position].song.name}",
									color=discord.Color.green()))
			if len(server.queue) > 1:
				queue = [queue.song.url for queue in server.queue][1:]
				await download_batch(queue)

	@playlist.command(name="list", description="Lists all the playlists")
	@discord.option("playlist-type", str, description="The type of the playlist", required=False, choices=["server", "user"], default="server", parameter_name="playlist_type", min_length=4, max_length=6)
	async def list_playlist(self, ctx: discord.ApplicationContext, playlist_type: str):
		await ctx.response.defer()
		async with database_context():
			playlists = await ((await Server.get(server_id=ctx.guild.id)).playlists.all() if playlist_type == "server" else (await Asker.get(discord_id=ctx.user.id)).playlists.all())
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
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def show(self, ctx: discord.ApplicationContext, name: str):
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			async with database_context():
				return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
										.add_field(name="Existing server playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in (await Server.get(server_id=ctx.guild.id)).playlists]))
										.add_field(name="Existing user playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in (await Asker.get(discord_id=ctx.user.id)).playlists])))
		embed = discord.Embed(title=name, color=discord.Color.green())
		async with database_context():
			playlist_songs = await (await Playlist.get(name=name)).songs.all()
			for index, playlist_song in enumerate(playlist_songs):
				song = playlist_song.song
				embed.add_field(name=f"{index + 1}.", value=f"__[{song.name}]({song.url})__")
				if index == 23 and len(playlist_songs) > 24:
					embed.add_field(name="...", value="")
					break
		await ctx.respond(embed=embed)

	@playlist.command(name="rename", description="Renames a playlist")
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	@discord.option("new-name", str, description="The new name of the playlist", required=True, parameter_name="new_name")
	async def rename(self, ctx: discord.ApplicationContext, name: str, new_name: str):
		await ctx.response.defer()
		if len(new_name) > 20:
			return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			async with database_context():
				server = await Server.get(server_id=ctx.guild.id)
				user_playlists = await (await Asker.get(discord_id=ctx.user.id)).playlists.all()
				return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
										.add_field(name="Existing server playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in server.playlists]))
										.add_field(name="Existing user playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in user_playlists]))
										)
		async with database_context():
			server = await Server.get(server_id=ctx.guild.id)
			if server is None:
				return
			if name not in [playlist.playlist.name for playlist in server.playlists]:
				return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
										.add_field(name="Existing playlists:",
													value="\n".join([playlist.playlist.name for playlist in server.playlists])))
			if new_name in [playlist.playlist.name for playlist in server.playlists]:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
										color=discord.Color.dark_red()))
			playlist = await Playlist.get(name=name)
			playlist.name = new_name
			await playlist.save()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.",
											  color=discord.Color.green()))

	@playlist.command(name="copy", description="Copies a playlist to another playlist type")
	@discord.option("name", str, description="The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))
	async def copy(self, ctx: discord.ApplicationContext, name: str):
		await ctx.response.defer()
		if name.endswith(" - SERVER"):
			name = name[:-9]
		elif name.endswith(" - USER"):
			name = name[:-7]
		else:
			async with database_context():
				return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
										.add_field(name="Existing server playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in (await Server.get(server_id=ctx.guild.id)).playlists]))
										.add_field(name="Existing user playlists:",
													value="\n- ".join([playlist.playlist.name for playlist in (await Asker.get(discord_id=ctx.user.id)).playlists])))
		async with database_context():
			playlist = await Playlist.get(name=name)
			if playlist is not None:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
										color=discord.Color.dark_red()))
			# Si la playlist est une playlist utilisateur
			if playlist in (await Asker.get(discord_id=ctx.user.id)).playlists:
				new_playlist = await Playlist.create(name=name)
				await new_playlist.save()
				await PlaylistSong.bulk_create((await Playlist.get(name=name)).songs)
				await UserPlaylist.create(playlist=new_playlist, user=(await Asker.get_or_create(discord_id=ctx.user.id))[0]).save()
			else:
				new_playlist = await Playlist.create(name=name)
				await new_playlist.save()
				await PlaylistSong.bulk_create((await Playlist.get(name=name)).songs)
				await ServerPlaylist.create(playlist=new_playlist, server=await Server.get(server_id=ctx.guild.id)).save()
		await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} copied.",
												color=discord.Color.green()))


def setup(bot):
	bot.add_cog(Playlists(bot))
