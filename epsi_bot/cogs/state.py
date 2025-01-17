import asyncio
import threading
from datetime import datetime
from typing import Optional

import discord
import pytubefix
from discord.commands import SlashCommandGroup
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError

from ..bot.bot import Bot
from ..utils import (Sinks,
				   EMBED_ERROR_BOT_NOT_CONNECTED,
				   Song,
				   Asker,
				   Server,
				   Queue,
				   database_context,
				   Research,
				   play_song,
				   download,
				   finished_record_callback,
				   YOUTUBE_REGEX,
				   GET_FILE_HTTP_URL
				   )


class State(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to the playing state of the bot"
		self.connections = {}

	play = SlashCommandGroup(name="play", description="Commands related to the audio of the bot")

	@play.command(name="url", description="Plays the audio of a file from an URL")
	@discord.option("url", str, description="The URL of the audio to play", required=True)
	async def play_url(self, ctx: discord.ApplicationContext, url: str):
		await ctx.response.defer()
		if ctx.user.id in [501303816302362635, 942531230291877910]:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Non mais tu me prends pour qui, je te connais hein",
									color=discord.Color.dark_red()))
		if YOUTUBE_REGEX.match(url):
			return await self.play_youtube(ctx, url)
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if not GET_FILE_HTTP_URL.match(url):
			return await ctx.respond(embed=discord.Embed(title="Error", description="Invalid URL.", color=discord.Color.dark_red()))
		if GET_FILE_HTTP_URL.match(url).group(1).split('.')[-1] not in ['mp3', 'wav', 'ogg', 'mp4']:
			return await ctx.respond(embed=discord.Embed(title="Error", description="Invalid URL.", color=discord.Color.dark_red()))
		async with database_context():
			server = await Server.get(server_id=ctx.guild.id)
			song, _ = await Song.get_or_create_important(["url"], name=GET_FILE_HTTP_URL.match(url).group(1).split('.')[0], url=url)
			asker, _ = await Asker.get_or_create(discord_id=ctx.author.id)	
			if not await server.queue.all():
				await Queue.create(server=server, song=song, position=0, asker=asker)
				await ctx.respond(embed=discord.Embed(title="Play",
													description=f"Playing song "
																f"[{GET_FILE_HTTP_URL.match(url).group(1).split('.')[0]}]({url})",
													color=discord.Color.green()))
				await play_song(ctx, url)
				return await asyncio.sleep(1)
			await Queue.create(server=server, song=song, position=len(server.queue), asker=asker)
			await ctx.respond(embed=discord.Embed(title="Queue",
												description=f"Song [{GET_FILE_HTTP_URL.match(url).group(1).split('.')[0]}]({url})"
															f" added to queue.",
												color=discord.Color.green()))

	@play.command(name="file", description="Plays the audio of a file")
	@discord.option("file", discord.Attachment, description="The file to play", required=True)
	async def play_file(self, ctx: discord.ApplicationContext, file: discord.Attachment):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if file.content_type not in ['audio/mpeg', 'audio/wav', 'audio/ogg', 'video/mp4']:
			return await ctx.respond(embed=discord.Embed(title="Error", description="File is not an audio file.",
														 color=discord.Color.dark_red()))
		if file.size > 10000000:
			return await ctx.respond(embed=discord.Embed(title="Error", description="File is too big.", color=discord.Color.dark_red()))
		url = file.url
		async with database_context():
			server = await Server.get(server_id=ctx.guild.id)
			song, _ = await Song.get_or_create_important(["url"], name=file.filename, url=url)
			asker, _ = await Asker.get_or_create(discord_id=ctx.author.id)
			if not await server.queue.all():
				await Queue.create(server=server, song=song, position=0, asker=asker)
				await ctx.respond(embed=discord.Embed(title="Play",
													description=f"Playing song [{file.filename}]({url})",
													color=discord.Color.green()))
				await play_song(ctx, url)
				return await asyncio.sleep(1)
			await Queue.create(server=server, song=song, position=len(server.queue), asker=asker)
			await ctx.respond(embed=discord.Embed(title="Queue",
												description=f"Song [{file.filename}]({url}) added to queue.",
												color=discord.Color.green()))

	@play.command(name="youtube", description="Plays the audio of a YouTube video")
	@discord.option("query", str, description="The YouTube audio to play", required=True)
	async def play_youtube(self, ctx: discord.ApplicationContext, query: str):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		try:
			url = pytubefix.YouTube(query).watch_url
			try:
				async with database_context():
					server = await Server.get(server_id=ctx.guild.id)
					if pytubefix.YouTube(url).length > 12000:
						return await ctx.respond(
							discord.Embed(title="Error",
										description=f"The video [{pytubefix.YouTube(url).title}]({url}) is too long",
										color=discord.Color.dark_red())
						)
					song, _ = await Song.get_or_create_important(["url"], name=pytubefix.YouTube(url).title, url=url)
					asker, _ = await Asker.get_or_create(discord_id=ctx.author.id)
					if not await server.queue.all():
						server.position = 0
						await Queue.create(server=server, song=song, position=0, asker=asker)
					else:
						await Queue.create(server=server, song=song, position=len(server.queue), asker=asker)
				if not ctx.guild.voice_client.is_playing():
					await ctx.respond(embed=discord.Embed(title="Play",
														  description=f"Playing song "
																	  f"[{pytubefix.YouTube(url).title}]({url})",
														  color=discord.Color.green()))
					await play_song(ctx, url)
				else:
					video = pytubefix.YouTube(url)
					threading.Thread(target=self._download, args=(url,), name=f"Download-{video.video_id}").start()
					await ctx.respond(embed=discord.Embed(title="Queue",
														  description=f"Song [{video.title}]({url})"
																	  f" added to queue.",
														  color=discord.Color.green()))
			except Exception as e:
				self.bot.logger.error(f"Error while adding song to queue: {e}")
				return await ctx.respond(
					embed=discord.Embed(title="Error", description=f"Error while adding song to queue. "
																   f"(Error: {e})", color=discord.Color.dark_red())
				)
		except PytubeRegexMatchError:
			videos = pytubefix.Search(query).videos
			if not videos:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="No results found.", color=discord.Color.dark_red()))
			view = Research(videos, ctx, False)
			# noinspection SqlDialectInspection
			await ctx.respond(
				embed=discord.Embed(title="Select audio",
									description=f"Select an audio to play for query `{query}` from the list below",
									color=discord.Color.green()), view=view)

	@staticmethod
	def _download(url: str):
		asyncio.run(download(url))

	@commands.slash_command(name="pause", description="Pauses the current song")
	async def pause(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if ctx.guild.voice_client.is_paused():
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="The song is already paused.", color=discord.Color.dark_red()))
		if not ctx.guild.voice_client.is_playing():
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="There is no song playing.", color=discord.Color.dark_red()))
		ctx.guild.voice_client.pause()
		await ctx.respond(embed=discord.Embed(title="Pause", description="Song paused.", color=discord.Color.green()))

	@commands.slash_command(name="resume", description="Resumes the current song")
	async def resume(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if not ctx.guild.voice_client.is_paused():
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="The song is not paused.", color=discord.Color.dark_red()))
		ctx.guild.voice_client.resume()
		await ctx.respond(embed=discord.Embed(title="Resume", description="Song resumed.", color=discord.Color.green()))

	@commands.slash_command(name="stop", description="Stops the current song")
	async def stop(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if not ctx.guild.voice_client.is_playing():
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="There is no song playing.", color=discord.Color.dark_red()))
		async with database_context():
			server = await Server.get(server_id=ctx.guild.id)
			server.position = 0
			await server.queue.all().delete()
			await server.save()
		ctx.guild.voice_client.stop()
		await ctx.respond(embed=discord.Embed(title="Stop", description="Song stopped.", color=discord.Color.green()))

	@commands.slash_command(name="volume", description="Gets or sets the volume of the bot")
	@discord.option("volume", int, description="The volume to set (from 0 to 100)", required=False, min_value=0, max_value=100)
	async def volume(self, ctx: discord.ApplicationContext, volume: Optional[int] = None):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if volume is not None:
			if volume > 100:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="Volume is too high.", color=discord.Color.dark_red()))
			if volume < 0:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="Volume is too low.", color=discord.Color.dark_red()))
			try:
				ctx.guild.voice_client.source.volume = volume / 100
			except AttributeError:
				pass
			async with database_context():
				server = await Server.get(server_id=ctx.guild.id)
				server.volume = volume
				await server.save()
			return await ctx.respond(embed=discord.Embed(title="Volume", description=f"Volume set to {volume}%",
														 color=discord.Color.green()))

		try:
			await ctx.respond(embed=discord.Embed(title="Volume",
												  description=f"Volume is "
															  f"{ctx.guild.voice_client.source.volume * 100}%",
												  color=discord.Color.green()))
		except AttributeError:
			# noinspection PyBroadException
			try:
				async with database_context():
					server = await Server.get(server_id=ctx.guild.id)
					await ctx.respond(embed=discord.Embed(title="Volume",
														description=f"Volume is {server.volume}%",
														color=discord.Color.green()))
			except Exception:
				await ctx.respond(
					embed=discord.Embed(title="Error", description="Error while getting volume.", color=discord.Color.dark_red()))

	@commands.slash_command(name="record",
							description="Enregistre nos chers gogols en train de chanter "
										"(c'est Rignchen qui m'as dit de laisser ça)")
	@discord.option("time", int, description="Le temps d'enregistrement en secondes (de 1s à 260s)", required=True, min_value=1, max_value=260)
	@discord.option("file-format", Sinks, description="Le format d'enregistrement", required=True)
	async def record(self, ctx: discord.ApplicationContext, time: int, file_format: Sinks):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if time > 260:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Time is too long.", color=discord.Color.dark_red()))
		if time < 1:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Time is too short.", color=discord.Color.dark_red()))
		vc = ctx.guild.voice_client
		if ctx.guild.id in self.connections.keys():
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Already recording", color=discord.Color.dark_red()))

		def finished_record():
			async def stop():
				vc.stop_recording()

			asyncio.run(stop())
			self.connections.pop(ctx.guild.id)

		if vc.channel.voice_states[vc.client.user.id].self_deaf:
			return await ctx.respond(embed=discord.Embed(title="Error", description="Bot is deafened.", color=discord.Color.dark_red()))
		vc.start_recording(
			file_format.value,
			finished_record_callback,
			ctx.channel,
			sync_start=True
		)
		self.connections[ctx.guild.id] = vc
		users = []
		for user in vc.channel.members:
			if not user.bot:
				users.append(user.mention)
		if not users:
			users = ["No one will be recorded"]
		await ctx.respond(
			f":⚠: {', '.join(users)}, {ctx.author.mention} is recording you for {time} seconds",
			embed=discord.Embed(title="Record",
								description=f"Recording for {time} seconds. The record will stop at "
											f"<t:{int(time + datetime.now().timestamp())}:R>.",
								color=discord.Color.green()))
		self.bot.loop.call_later(time, finished_record)

	@commands.slash_command(name="stop_record", description="Arrête l'enregistrement")
	async def stop_record(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		try:
			ctx.guild.voice_client.stop_recording()
			self.connections.pop(ctx.guild.id).cancel()
			await ctx.respond(embed=discord.Embed(title="Stop record", description="Stopped recording.",
												  color=discord.Color.green()))
		except Exception as e:
			await ctx.respond(embed=discord.Embed(title="Error", description=f"Error while stopping recording: {e}",
												  color=discord.Color.dark_red()))


def setup(bot):
	bot.add_cog(State(bot))
