import asyncio
import time
from typing import cast

import discord.voice
import pytubefix
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.sinks import RecordingException
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError

from epsi_bot.bot.bot import Bot
from epsi_bot.utils.audio import finished_record_callback, get_youtube, play_song
from epsi_bot.utils.cache import download
from epsi_bot.utils.constants import (
	EMBED_ERROR_BOT_NOT_CONNECTED,
	GET_FILE_HTTP_URL,
	MAX_TRACK_LENGTH,
	YOUTUBE_CLIENT,
	YOUTUBE_REGEX,
)
from epsi_bot.utils.models import Queue, Server, Song, User
from epsi_bot.utils.type_utils import GuildMessageable, Sinks, get_guild, option
from epsi_bot.utils.views import Research


class State(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to the playing state of the bot"
		self.connections: dict[
			int, discord.voice.VoiceClient
		] = {}  # Guild ID to VoiceClient mapping

	play = SlashCommandGroup(
		name="play", description="Commands related to the audio of the bot"
	)

	@play.command(name="url", description="Plays the audio of a file from an URL")
	@option("url", str, description="The URL of the audio to play", required=True)
	async def play_url(self, ctx: discord.ApplicationContext, url: str) -> None:
		if ctx.user.id == 501303816302362635:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Non mais tu me prends pour qui, je te connais hein",
					color=discord.Color.dark_red(),
				)
			)
			return
		await ctx.response.defer()
		guild = get_guild(ctx)
		if YOUTUBE_REGEX.match(url):
			await self.play_youtube(ctx, url)
			return
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return

		url_match = GET_FILE_HTTP_URL.match(url)
		if not url_match:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Invalid URL.",
					color=discord.Color.dark_red(),
				)
			)
			return

		filename = url_match.group(1)
		file_extension = filename.split(".")[-1]
		if file_extension not in ["mp3", "wav", "ogg", "mp4"]:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Invalid URL.",
					color=discord.Color.dark_red(),
				)
			)
			return

		server = await Server.get(server_id=guild.id)
		song_name = filename.split(".")[0]
		song, _ = await Song.get_or_create(url=url, defaults={"name": song_name})
		user, _ = await User.get_or_create(user_id=ctx.author.id)

		if not await server.queue.all():
			await Queue.create(server=server, song=song, position=0, asker=user)
			await ctx.respond(
				embed=discord.Embed(
					title="Play",
					description=f"Playing song [{song_name}]({url})",
					color=discord.Color.green(),
				)
			)
			await play_song(ctx, url)
			await asyncio.sleep(1)
			return

		await Queue.create(
			server=server, song=song, position=len(server.queue), asker=user
		)
		await ctx.respond(
			embed=discord.Embed(
				title="Queue",
				description=f"Song [{song_name}]({url}) added to queue.",
				color=discord.Color.green(),
			)
		)

	@play.command(name="file", description="Plays the audio of a file")
	@option("file", discord.Attachment, description="The file to play", required=True)
	async def play_file(
		self, ctx: discord.ApplicationContext, file: discord.Attachment
	) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		if file.content_type not in [
			"audio/mpeg",
			"audio/wav",
			"audio/ogg",
			"video/mp4",
		]:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="File is not an audio file.",
					color=discord.Color.dark_red(),
				)
			)
			return
		if file.size > 10000000:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="File is too big.",
					color=discord.Color.dark_red(),
				)
			)
			return
		url = file.url
		server = await Server.get(server_id=guild.id)
		song, _ = await Song.get_or_create(url=url, defaults={"name": file.filename})
		user, _ = await User.get_or_create(user_id=ctx.author.id)
		if not await server.queue.all():
			await Queue.create(server=server, song=song, position=0, asker=user)
			await ctx.respond(
				embed=discord.Embed(
					title="Play",
					description=f"Playing song [{file.filename}]({url})",
					color=discord.Color.green(),
				)
			)
			await play_song(ctx, url)
			await asyncio.sleep(1)
			return
		await Queue.create(
			server=server, song=song, position=len(server.queue), asker=user
		)
		await ctx.respond(
			embed=discord.Embed(
				title="Queue",
				description=f"Song [{file.filename}]({url}) added to queue.",
				color=discord.Color.green(),
			)
		)

	@play.command(name="youtube", description="Plays the audio of a YouTube video")
	@option("query", str, description="The YouTube audio to play", required=True)
	async def play_youtube(self, ctx: discord.ApplicationContext, query: str) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		try:
			video = get_youtube(query)
			url = video.watch_url
			server = await Server.get(server_id=guild.id).prefetch_related(
				"queue", "queue__song"
			)
			if video.length > MAX_TRACK_LENGTH:
				await ctx.respond(
					discord.Embed(
						title="Error",
						description=f"The video [{video.title}]({url}) is too long",
						color=discord.Color.dark_red(),
					)
				)
				return
			song, _ = await Song.get_or_create(url=url, defaults={"name": video.title})
			user, _ = await User.get_or_create(user__id=ctx.author.id)
			if not await server.queue.all():
				server.position = 0
				await Queue.create(server=server, song=song, position=0, asker=user)
			else:
				await Queue.create(
					server=server, song=song, position=len(server.queue), asker=user
				)
			if not guild.voice_client.is_playing():
				await ctx.respond(
					embed=discord.Embed(
						title="Play",
						description=f"Playing song [{video.title}]({video.watch_url})",
						color=discord.Color.green(),
					)
				)
				await play_song(ctx, url)
			else:
				asyncio.create_task(download(url), name=f"Download-{video.video_id}")
				await ctx.respond(
					embed=discord.Embed(
						title="Queue",
						description=f"Song [{video.title}]({url}) added to queue.",
						color=discord.Color.green(),
					)
				)
		except PytubeRegexMatchError:
			videos = pytubefix.Search(query, client=YOUTUBE_CLIENT).videos
			if not videos:
				await ctx.respond(
					embed=discord.Embed(
						title="Error",
						description="No results found.",
						color=discord.Color.dark_red(),
					)
				)
				return
			view = Research(videos, ctx, False)
			# noinspection SqlDialectInspection
			await ctx.respond(
				embed=discord.Embed(
					title="Select audio",
					description=f"Select an audio to play for query `{query}` from the list below",
					color=discord.Color.green(),
				),
				view=view,
			)

	@commands.slash_command(name="pause", description="Pauses the current song")
	async def pause(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		if guild.voice_client.is_paused():
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="The song is already paused.",
					color=discord.Color.dark_red(),
				)
			)
			return
		if not guild.voice_client.is_playing():
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="There is no song playing.",
					color=discord.Color.dark_red(),
				)
			)
			return
		guild.voice_client.pause()
		await ctx.respond(
			embed=discord.Embed(
				title="Pause", description="Song paused.", color=discord.Color.green()
			)
		)

	@commands.slash_command(name="resume", description="Resumes the current song")
	async def resume(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		if not guild.voice_client.is_paused():
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="The song is not paused.",
					color=discord.Color.dark_red(),
				)
			)
			return
		guild.voice_client.resume()
		await ctx.respond(
			embed=discord.Embed(
				title="Resume", description="Song resumed.", color=discord.Color.green()
			)
		)

	@commands.slash_command(name="stop", description="Stops the current song")
	async def stop(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		if not guild.voice_client.is_playing():
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="There is no song playing.",
					color=discord.Color.dark_red(),
				)
			)
			return
		server = await Server.get(server_id=guild.id)
		server.position = 0
		await server.queue.all().delete()
		await server.save()
		guild.voice_client.stop()
		await ctx.respond(
			embed=discord.Embed(
				title="Stop", description="Song stopped.", color=discord.Color.green()
			)
		)

	@commands.slash_command(
		name="volume", description="Gets or sets the volume of the bot"
	)
	@option(
		"volume",
		int,
		description="The volume to set (from 0 to 100)",
		required=False,
		min_value=0,
		max_value=100,
	)
	async def volume(
		self, ctx: discord.ApplicationContext, volume: int | None = None
	) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if (voice_client := guild.voice_client) is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		if volume is not None:
			if (source := voice_client.source) is None:
				await ctx.respond(
					embed=discord.Embed(
						title="Volume",
						description="No audio is playing.",
						color=discord.Color.red(),
					)
				)
				return
			cast(
				discord.PCMVolumeTransformer[discord.FFmpegPCMAudio], source
			).volume = volume / 100

			server = await Server.get(server_id=guild.id)
			server.volume = volume
			await server.save()
			await ctx.respond(
				embed=discord.Embed(
					title="Volume",
					description=f"Volume set to {volume}%",
					color=discord.Color.green(),
				)
			)
			return
		await ctx.respond(
			embed=discord.Embed(
				title="Volume",
				description=f"Volume is "
				f"{cast(discord.PCMVolumeTransformer[discord.FFmpegPCMAudio], voice_client.source).volume * 100}%",
				color=discord.Color.green(),
			)
		)

	@commands.slash_command(
		name="record",
		description="Enregistre nos chers gogols en train de chanter "
		"(c'est Rignchen qui m'as dit de laisser ça)",
	)
	@option(
		"duration",
		int,
		description="Le temps d'enregistrement en secondes (de 1s à 260s)",
		required=True,
		min_value=1,
		max_value=260,
	)
	@option(
		"file-format", Sinks, description="Le format d'enregistrement", required=True
	)
	async def record(
		self, ctx: discord.ApplicationContext, duration: int, file_format: Sinks
	) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		vc = guild.voice_client
		if guild.id in self.connections:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Already recording",
					color=discord.Color.dark_red(),
				)
			)
			return

		def finished_record() -> None:
			async def stop() -> None:
				vc.stop_recording()

			asyncio.run_coroutine_threadsafe(stop(), ctx.bot.loop)
			self.connections.pop(guild.id)

		if cast(discord.VoiceChannel, vc.channel).voice_states[vc.user.id].self_deaf:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Bot is deafened.",
					color=discord.Color.dark_red(),
				)
			)
			return
		sink = file_format.sink()

		def on_finished(exc: Exception | None) -> None:
			if exc is not None:
				self.bot.logger.error("Recording ended with an error", exc_info=exc)
			asyncio.run_coroutine_threadsafe(
				finished_record_callback(sink, cast(GuildMessageable, ctx.channel)),
				ctx.bot.loop,
			)

		vc.start_recording(sink, on_finished, sync_start=True)
		self.connections[guild.id] = vc
		users = []
		for user in cast(discord.VoiceChannel, vc.channel).members:
			if not user.bot:
				users.append(user.mention)
		text: str
		if users:
			text = f":⚠: {', '.join(users)}, {ctx.author.mention} is recording you for {duration} seconds"
		else:
			text = f"{ctx.author.mention}, there's no one to record"
		await ctx.respond(
			text,
			embed=discord.Embed(
				title="Record",
				description=f"Recording for {duration} seconds. The record will stop at "
				f"<t:{int(time.time() + duration)}:R>.",
				color=discord.Color.green(),
			),
		)
		self.bot.loop.call_later(duration, finished_record)

	@commands.slash_command(name="stop_record", description="Arrête l'enregistrement")
	async def stop_record(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		try:
			self.connections.pop(guild.id).stop_recording()
			await ctx.respond(
				embed=discord.Embed(
					title="Stop record",
					description="Stopped recording.",
					color=discord.Color.green(),
				)
			)
		except RecordingException, KeyError:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="There is no recording in progress.",
					color=discord.Color.dark_red(),
				)
			)


def setup(bot: Bot) -> None:
	bot.add_cog(State(bot))
