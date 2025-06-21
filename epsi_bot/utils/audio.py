import asyncio
import io
import logging
import random

import discord
import discord.ext.pages
import pytubefix  # type: ignore[import-untyped]
from discord.ext import commands
from ffmpeg.asyncio import FFmpeg  # type: ignore[import-untyped]
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError  # type: ignore[import-error]

from epsi_bot.utils.cache import download
from epsi_bot.utils.constants import YOUTUBE_CLIENT, MAX_TRACK_LENGTH, EMBED_ERROR_VIDEO_TOO_LONG
from epsi_bot.utils.loggers import get_logger
from epsi_bot.utils.models import Server, Song, SongListenCount, database_context
from epsi_bot.utils.type_utils import FfmpegFormats


__all__ = [
	"finished_record_callback",
	"disconnect_from_channel",
	"get_index_from_title",
	"play_song",
	"convert",
	"get_youtube",
	"get_lyrics"
]


async def finished_record_callback(sink: discord.sinks.Sink, channel: discord.TextChannel) -> None:
	"""Callback function to execute when the recording is finished that processes the audio and sends it to the
	channel"""
	mention_strs = []
	files: list[discord.File] = []

	# Collect user mentions
	for user_id in sink.audio_data.keys():
		mention_strs.append(f"<@{user_id}>")

	message = await channel.send(
		f"## Recorded {', '.join(mention_strs)}\nProcessing audio" if
		len(mention_strs) > 1 else f"Recorded {mention_strs[0]}\nProcessing audio" if
		len(mention_strs) == 1 else "Recorded no one"
	)

	# Process individual user audio files
	audio_streams = []
	for user_id, audio in sink.audio_data.items():
		audio.file.seek(0)
		audio_streams.append(audio.file.read())
		audio.file.seek(0)

		member = channel.guild.get_member(user_id)
		if member is not None:
			files.append(discord.File(audio.file, filename=f"{member.name}.{getattr(sink, 'encoding', 'wav')}"))

	# Merge audio using FFmpeg
	if len(audio_streams) > 0:
		merged_audio = await merge_audio_streams(audio_streams, getattr(sink, "encoding", "wav"))
		with io.BytesIO(merged_audio) as f:
			await message.edit(
				content=f"## Recorded {', '.join(mention_strs)}" if len(
					mention_strs) > 1 else f"Recorded {mention_strs[0]}" if len(
					mention_strs) == 1 else "Recorded no one",
				files=files + [discord.File(f, filename=f"record.{getattr(sink, 'encoding', 'wav')}")] if getattr(
					sink, "encoding", "wav") != "wav" else files
			)

async def merge_audio_streams(audio_streams: list[bytes], format_name: str = "wav") -> bytes:
	"""Merge multiple audio streams using FFmpeg"""
	if len(audio_streams) == 0:
		return b''
	if len(audio_streams) == 1:
		return audio_streams[0]

	# Create FFmpeg complex filter to merge audio
	inputs = []

	for i in range(len(audio_streams)):
		inputs.append(f"[{i}:a]")

	filter_str = f"{' '.join(inputs)}amix=inputs={len(audio_streams)}:dropout_transition=0[out]"

	# Setup FFmpeg command
	ffmpeg = FFmpeg("ffmpeg")

	# Add inputs
	for i, stream in enumerate(audio_streams):
		ffmpeg = ffmpeg.input(f"pipe:{i}", format=format_name)

	# Add filter complex and output
	ffmpeg = ffmpeg.filter_complex(filter_str).output("pipe:out", map="[out]", format=format_name)

	# Execute FFmpeg with all input streams
	result = await ffmpeg.execute(
		*audio_streams,
		stdout=True,
		stderr=True
	)
	return result


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
	return None


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
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
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
			server.position = random.sample(list(set(range(0, len(server.queue))) - {server.position}), 1)[0]
			await server.save()
		try:
			await play_song(ctx, server.queue[server.position].song.url)
		except Exception as e:
			get_logger("Bot").error(f"Error while playing song: {e}")


async def play_song(ctx: discord.ApplicationContext, url: str, direct_play: bool = False) -> None:
	"""
	Play a song from a URL
	Parameters
	----------
	ctx : discord.ApplicationContext
		The context of the command
	url : str
		The URL of the song to play
	direct_play : bool
		If True, the song will be played as a direct stream without downloading it.
		A download will still occur for processing through ffmpeg
	"""
	if ctx.guild.voice_client is None:
		return
	if ctx.guild.voice_client.is_playing():
		ctx.guild.voice_client.stop()
	loop = asyncio.get_event_loop()
	async with database_context():
		server = await Server.get(server_id=ctx.guild.id)
		song = await Song.get(url=url)
		song_listen_count = await SongListenCount.get_or_none(song=song)
		if song_listen_count is not None:
			song_listen_count.count += 1
			await song_listen_count.save()
		else:
			await SongListenCount.create(song=song, count=1)
	to_play: str | io.BytesIO
	pipe = direct_play
	before_options = None
	if direct_play:
		to_play = url
		before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
	else:
		try:
			video = get_youtube(url)
			if video.age_restricted:
				await ctx.respond(
					embed=discord.Embed(title="Error", description=f"The [video]({url}) is age restricted",
					                    color=discord.Color.dark_red()))
				return
			if video.length > MAX_TRACK_LENGTH:
				await ctx.respond(embed=EMBED_ERROR_VIDEO_TOO_LONG)
				return
			to_play = await download(url)
		except PytubeRegexMatchError:
			to_play = await download(url)
	player = discord.PCMVolumeTransformer(
		discord.FFmpegPCMAudio(
			to_play,
			executable="ffmpeg",
			pipe=pipe,
			before_options=before_options
		),
		server.volume / 100
	)
	try:
		get_logger("Bot").info(f"Playing song {url}")
		_ = ctx.guild.voice_client.play(player,
		                            after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e),
		                                                                             loop),
		                            wait_finish=True)
	except discord.errors.ClientException:
		while ctx.guild.voice_client.is_playing():
			await asyncio.sleep(0.1)
		get_logger("Bot").info(f"Playing song {url}")
		_ = ctx.guild.voice_client.play(player,
		                            after=lambda e: asyncio.run_coroutine_threadsafe(on_play_song_finished(ctx, e),
		                                                                             loop),
		                            wait_finish=True)


async def on_play_song_finished(ctx: discord.ApplicationContext, error: Exception | None = None) -> None:
	"""Callback function to execute when a song is finished"""
	if error:
		get_logger("Bot").error("Error:", error)
		await ctx.respond(
			embed=discord.Embed(title="Error", description="An error occurred while playing the song.",
			                    color=discord.Color.dark_red()))
	get_logger("Bot").info("Song finished")
	await change_song(ctx)


async def convert(audio: io.BytesIO, file_format: FfmpegFormats, log: logging.Logger = get_logger("Audio-Converter"),
                  executable: str = "ffmpeg") -> io.BytesIO:
	"""Convert an audio file to another format"""
	ffmpeg = (
		FFmpeg(executable)
		.input('pipe:0')
		.output("pipe:1", file_format.value, f=file_format.name.lower())
	)
	byte = await ffmpeg.execute(audio.getvalue())
	log.info(f"Converted audio to {file_format}")
	return io.BytesIO(byte)


def get_youtube(url: str) -> pytubefix.YouTube:
	"""Get a YouTube video from a URL"""
	return pytubefix.YouTube(url, client=YOUTUBE_CLIENT)


def get_lyrics(title: str) -> str:
	"""Get the lyrics of a song"""
	return title
