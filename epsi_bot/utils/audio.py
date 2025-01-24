import asyncio
import io
import logging
import random

import discord
import discord.ext.pages
from ffmpeg.asyncio import FFmpeg  # type: ignore[import-untyped]
import pydub  # type: ignore[import-untyped]
import pytubefix  # type: ignore[import-untyped]
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError # type: ignore[import-error]

from .models import Server, Song, SongListenCount, database_context
from .loggers import get_logger
from .cache import download
from .types import FfmpegFormats

pydub.AudioSegment.converter = "ffmpeg"

__all__ = [
	"finished_record_callback",
	"disconnect_from_channel",
	"get_index_from_title",
	"play_song",
	"convert",
	"get_lyrics"
]


async def finished_record_callback(sink: discord.sinks.Sink, channel: discord.TextChannel) -> None:
	"""Callback function to execute when the recording is finished that processes the audio and sends it to the
	channel"""
	mention_strs = []
	audio_segs: list[pydub.AudioSegment] = []
	files: list[discord.File] = []

	longest = pydub.AudioSegment.empty()
	for user_id in sink.audio_data.keys():
		mention_strs.append(f"<@{user_id}>")
	message = await channel.send(
		f"## Recorded {', '.join(mention_strs)}\nProcessing audio" if
		len(mention_strs) > 1 else f"Recorded {mention_strs[0]}\nProcessing audio" if
		len(mention_strs) == 1 else "Recorded no one"
	)
	for user_id, audio in sink.audio_data.items():
		user_id: int
		seg = pydub.AudioSegment.from_file(audio.file, format=sink.encoding)

		# Determine the longest audio segment
		if len(seg) > len(longest):
			audio_segs.append(longest)
			longest = seg
		else:
			audio_segs.append(seg)

		audio.file.seek(0)
		member = channel.guild.get_member(user_id)
		if member is not None:
			files.append(discord.File(audio.file, filename=f"{member.name}.{sink.encoding}"))

	for seg in audio_segs:
		longest = longest.overlay(seg)
	with io.BytesIO() as f:
		longest.export(f, format=sink.encoding)
		await message.edit(content=f"## Recorded {', '.join(mention_strs)}" if len(
			mention_strs) > 1 else f"Recorded {mention_strs[0]}" if len(
			mention_strs) == 1 else "Recorded no one",
						   files=files + [
							   discord.File(f, filename=f"record.{sink.encoding}")] if sink.encoding != "wav" else files
						   )


async def disconnect_from_channel(state: discord.VoiceState, bot: commands.Bot) -> None:
	"""Callback function to execute when the bot has to disconnect from a voice channel"""
	ok = False
	for client in bot.voice_clients:
		for guild in client.client.guilds:
			if state.channel is None:
				return await client.disconnect(force=True)
			if guild.id == state.channel.guild.id:
				await client.disconnect(force=True)
				async with database_context():
					server = await Server.get(server_id=guild.id)
					await server.queue.all().delete()
					server.position = 0
					await server.save()
				ok = True
			if ok:
				break
		if ok:
			break




def get_index_from_title(title: str, list_to_check: list[Song]) -> int:
	"""Get the index of a song in a list of songs from its title.""" 
	for index, song in enumerate(list_to_check):
		if song.name == title:
			return index
	return -1


async def change_song(ctx: discord.ApplicationContext) -> None:
	"""Callback function to execute when a song is finished to change the song taking into account the server's
	configuration"""
	async with database_context():
		server = await Server.get(server_id=ctx.guild.id)
		if not await server.queue.all():
			return
		if server.loop_song:
			pass
		elif server.loop_queue or server.position < len(server.queue) - 1:
			server.position = (server.position + 1) % len(server.queue)
			await server.save()
		else:
			return
		if server.random and len(server.queue) > 1:
			server.position = random.sample(set(range(0, len(server.queue))) - {server.position}, 1)[0]
			await server.save()
		try:
			await play_song(ctx, server.queue[server.position].song.url)
		except Exception as e:
			get_logger("Bot").error(f"Error while playing song: {e}")


async def play_song(ctx: discord.ApplicationContext, url: str) -> None:
	"""Play a song from a URL"""
	if ctx.guild.voice_client is None:
		return
	if ctx.guild.voice_client.is_playing():
		ctx.guild.voice_client.stop()
	loop = asyncio.get_event_loop()
	async with database_context():
		server = await Server.get(server_id=ctx.guild.id)
		song = await Song.get(url=url)
		song_listen_lount = await SongListenCount.get_or_none(song=song)
		if song_listen_lount is not None:
			song_listen_lount.count += 1
			await song_listen_lount.save()
		else:
			await SongListenCount.create(song=song, count=1)
	try:
		video = pytubefix.YouTube(url)
		if video.age_restricted:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description=f"The [video]({url}) is age restricted",
									color=discord.Color.dark_red()))
		if video.length > 12000:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description=f"The video [{video.title}]({url}) is too long",
									color=discord.Color.dark_red()))
		file = await download(url)
		buffer = io.BytesIO()
		stream = video.streams.get_audio_only()
		stream.stream_to_buffer(buffer)
		buffer.seek(0)
		player = discord.PCMVolumeTransformer(
			discord.FFmpegPCMAudio(file, executable="ffmpeg", pipe=True),
			server.volume / 100)
		try:
			get_logger("Bot").info(f"Playing song {video.title}")
			ctx.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e), loop),
										wait_finish=True)

		except discord.errors.ClientException:
			while ctx.guild.voice_client.is_playing():
				await asyncio.sleep(0.1)
			get_logger("Bot").info(f"Playing song {video.title}")
			ctx.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e), loop),
										wait_finish=True)
	except PytubeRegexMatchError:
		file = await download(url)
		player = discord.PCMVolumeTransformer(
			discord.FFmpegPCMAudio(file, executable="ffmpeg", pipe=True),
			server.volume / 100)
		try:
			get_logger("Bot").info(f"Playing song {url}")
			ctx.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e), loop),
										wait_finish=True)
		except discord.errors.ClientException:
			try:
				await ctx.guild.voice_client.disconnect(force=True)
			except discord.errors.ClientException:
				pass
			await ctx.author.voice.channel.connect()
			get_logger("Bot").info(f"Playing song {url}")
			ctx.guild.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e), loop),
										wait_finish=True)


async def on_play_song_finished(ctx: discord.ApplicationContext, error: Exception | None=None) -> None:
	"""Callback function to execute when a song is finished"""
	if error:
		get_logger("Bot").error("Error:", error)
		await ctx.respond(
			embed=discord.Embed(title="Error", description="An error occurred while playing the song.", color=discord.Color.dark_red()))
	get_logger("Bot").info("Song finished")
	await change_song(ctx)


async def convert(audio: io.BytesIO, file_format: FfmpegFormats, log: logging.Logger = get_logger("Audio-Converter"), executable: str = "ffmpeg") -> io.BytesIO:
	"""Convert an audio file to another format"""
	ffmpeg = (
		FFmpeg(executable)
		.input('pipe:0')
		.output("pipe:1", file_format.value, f=file_format.name.lower())
	)
	byte = await ffmpeg.execute(audio.getvalue())
	log.info(f"Converted audio to {file_format}")
	return io.BytesIO(byte)


def get_lyrics(title: str) -> str:
	"""Get the lyrics of a song"""
	return title