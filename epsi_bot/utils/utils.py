import asyncio
import io
import logging
import random
import re
from typing import Any
import zlib
import base64
import binascii
from enum import Enum

import discord
import discord.ext.pages
from ffmpeg.asyncio import FFmpeg  # type: ignore[import-untyped]
import pydub  # type: ignore[import-untyped]
import pytubefix  # type: ignore[import-untyped]
from aiocache import MemcachedCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer  # type: ignore[import-untyped]
from discord.ext import commands
from pytubefix.exceptions import RegexMatchError as PytubeRegexMatchError # type: ignore[import-error]

from .constants import EMBED_ERROR_BOT_NOT_CONNECTED
from .async_ import AsyncRequests
from .models import Asker, Server, Song, Playlist, Queue, SongListenCount, get_user_playlists
from .loggers import get_logger

pydub.AudioSegment.converter = "ffmpeg"

__all__ = [
	"AudioCache",
	"download",
	"Sinks",
	"finished_record_callback",
	"disconnect_from_channel",
	"Research",
	"get_playlists",
	"get_playlists_songs",
	"get_queue_songs",
	"get_index_from_title",
	"play_song",
	"FfmpegFormats",
	"convert",
	"get_lyrics"
]


class AudioCache(MemcachedCache):
	"""Class to manage the audio cache"""
	def __init__(self, pool_size: int=5):
		super().__init__(
			serializer=AudioCache.Base64Serializer(),
			namespace="audio",
			endpoint="127.0.0.1",
			port=11211,
			pool_size=pool_size,
			timeout=15
		)
		self.logger = get_logger("Memcached Audio Cache")

	async def get(self, key: str, **_: Any) -> io.BytesIO | None:
		"""Get a value from the cache"""
		return (await super().get(key)) or None
	
	async def set(self, key: str, value: io.BytesIO, ttl: int = 3600, **_: Any) -> None:
		"""Set a value in the cache"""
		await super().set(key, value, ttl=ttl)	
		self.logger.debug(f"Set {key} in cache")

	async def exists(self, key: str, **_: Any) -> bool:
		"""Check if a key exists in the cache"""
		return await super().exists(key)
	
	def update_ttl(self, key: str, new_ttl: int) -> None:
		"""Update the ttl of a key in the cache"""
		key = self.build_key(key, namespace=self.namespace)
		self.client.touch(key.encode(), new_ttl)
	
	async def clear(self, **_: Any) -> None:
		"""Clear the cache"""
		await super().clear()

	def __aenter__(self) -> "AudioCache":
		return super().__aenter__()

	def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
		return super().__aexit__(exc_type, exc_val, exc_tb)
	
	class Base64Serializer(JsonSerializer):
		def dumps(self, value):
			if isinstance(value, io.BytesIO):
				logger = get_logger("Memcached")
				logger.debug(f"Audio size: {len(value.getvalue())} bytes")
				compressed = zlib.compress(base64.b64encode(value.getvalue()))
				logger.debug(f"Compressed audio size: {len(compressed)} bytes")
				return binascii.hexlify(compressed).decode()
			return super().dumps(value)

		def loads(self, value: str):
			try:
				val = io.BytesIO(base64.b64decode(zlib.decompress(binascii.unhexlify(value.encode()))))
				val.seek(0)
				return val
			except (TypeError, binascii.Error, zlib.error, AttributeError):
				return super().loads(value)

async def to_cache(url: str, cache: AudioCache) -> io.BytesIO:
	data = await cache.get(url)
	if data is not None:
		return data
	buffer = io.BytesIO()
	buffer.seek(0)
	youtube_regex = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/((watch\?v=)|(embed/)|(v/)|(.+\?v=))?([^&=%?]{11})')
	if not youtube_regex.match(url):
		r: bytes = await AsyncRequests.get(url, return_type="content")
		buffer.write(r)
	else:
		yt_video = pytubefix.YouTube(url)
		stream = yt_video.streams.get_audio_only()
		stream.stream_to_buffer(buffer)
	buffer.seek(0)
	await cache.set(url, buffer, ttl=3600)
	return buffer

async def download(url: str, download_logger: logging.Logger = get_logger("Audio-Downloader")) -> io.BytesIO:
	"""
	Download a video from a YouTube (or other) URL.
	
	Parameters
	----------
	url : str
		The URL of the video to download
	download_logger : logging.Logger
		The logger to log the download
	
	Returns
	-------
	Optional[io.BytesIO]
		The downloaded video
	"""
	async with AudioCache() as cache:
		value = await to_cache(url, cache)
	download_logger.info(f"Succesfully downloaded {url}")
	return value
	
	
async def download_batch(urls: list[str], download_logger: logging.Logger = get_logger("Audio-Downloader")) -> list[io.BytesIO]:
	"""
	Download a list of videos from YouTube (or other) URLs.
	
	Parameters
	----------
	urls : list[str]
		The URLs of the videos to download
	download_logger : logging.Logger
		The logger to log the download
	
	Returns
	-------
	list[io.BytesIO]
		The downloaded videos
	"""

	async def download_worker(url: str, cache_) -> io.BytesIO:
		result = await to_cache(url, cache_)
		download_logger.info(f"Downloaded {url}")
		return result
	
	async with AudioCache(40) as cache:
		tasks = [download_worker(url, cache) for url in urls]
		results = await asyncio.gather(*tasks)
		return results

class Sinks(Enum):
	"""Enum for the different types of audio sinks"""
	mp3 = discord.sinks.MP3Sink()
	wav = discord.sinks.WaveSink()
	ogg = discord.sinks.OGGSink()
	mp4 = discord.sinks.MP4Sink()


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
				server: Server = Server.get(server_id=guild.id)
				for queue_elem in server.queue:
					queue_elem.delete().execute()
				server.position = 0
				server.save()
				ok = True
			if ok:
				break
		if ok:
			break


class SelectVideo(discord.ui.Select):
	"""
	Select menu to select a video to play
	
	Parameters
	----------
	videos : list[pytubefix.YouTube]
		The list of videos to select from
	ctx : discord.ApplicationContext
		The context of the command
	download_file : bool
		Whether to download the file or not (useful for the download command)
	*args
		discord.ui.Select arguments
	**kwargs
		discord.ui.Select keyword arguments

	Methods
	-------
	callback(interaction: discord.Interaction)
		The callback function to execute when a video is selected
	"""

	def __init__(self, videos: list[pytubefix.YouTube], ctx: discord.ApplicationContext, download_file: bool, *args,
				 **kwargs):
		super().__init__(*args, **kwargs)
		self.placeholder = "Select an audio to play"
		self.min_values = 1
		self.max_values = 1
		self.ctx = ctx
		self.download = download_file
		options: list[discord.SelectOption] = []
		for video in videos:
			if any(option.value == video.watch_url for option in options):
				continue
			options.append(discord.SelectOption(label=video.title, value=video.watch_url))
		self.options = options

	async def callback(self, interaction: discord.Interaction):
		# Si l'utilisateur à l'origine du select n'est pas l'utilisateur à l'origine de l'interaction, on ignore.
		if interaction.user.id != self.ctx.author.id:
			return await interaction.response.send_message("You are not the author of the command.", ephemeral=True)
		await interaction.message.edit(
			embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}",
								color=discord.Color.green()), view=None)
		server: Server = Server.get(server_id=interaction.guild.id)
		if self.download:
			if pytubefix.YouTube(self.values[0]).length > 12000:
				return await interaction.message.edit(embed=discord.Embed(title="Error",
																		  description=f"The video "
																					  f"""[{pytubefix.YouTube(self.values[0])
																		  .title}]({self.values[0]}) is too long""",
																		  color=discord.Color.dark_red()))
			
			stream = pytubefix.YouTube(self.values[0]).streams.get_audio_only()
			buffer = io.BytesIO()
			stream.stream_to_buffer(buffer)
			buffer.seek(0)
			return await interaction.message.edit(
				embed=discord.Embed(title="Download", description="Song downloaded.", color=discord.Color.green()),
				file=discord.File(buffer, filename=f"{stream.title}.mp3"),
				view=None)
		if not server.queue:
			server.position = 0
			server.save()
			yt_video = pytubefix.YouTube(self.values[0])
			song, _ = Song.get_or_create_important(["url"], url=self.values[0], name=yt_video.title)
			asker, _ = Asker.get_or_create(discord_id=interaction.user.id)
			Queue.create(song=song, asker=asker, position=0, server=server)
		else:
			yt_video = pytubefix.YouTube(self.values[0])
			song, _ = Song.get_or_create_important(["url"], url=self.values[0], name=yt_video.title)
			asker, _ = Asker.get_or_create(discord_id=interaction.user.id)
			Queue.create(song=song, asker=asker, position=len(server.queue), server=server)
		if interaction.guild.voice_client is None:
			return await interaction.message.edit(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if not interaction.guild.voice_client.is_playing():
			await interaction.message.edit(embed=discord.Embed(title="Play",
															   description=f"Playing song "
																		   f"[{pytubefix.YouTube(self.values[0]).title}]"
																		   f"({self.values[0]})",
															   color=discord.Color.green()))
			await play_song(self.ctx, server.queue[server.position].song.url)
		else:
			await interaction.message.edit(embed=discord.Embed(title="Queue",
															   description=f"Song "
																		   f"[{pytubefix.YouTube(self.values[0]).title}]"
																		   f"({self.values[0]}) added to queue.",
															   color=discord.Color.green()))


class Research(discord.ui.View):
	"""
	View to search for a video to play using a select menu

	Parameters
	----------
	videos : list[pytubefix.YouTube]
		The list of videos to select from
	ctx : discord.ApplicationContext
		The context of the command
	download_file : bool
		Whether to download the file or not (useful for the download command)
	*items
		discord.ui.View items
	timeout : float
		The timeout of the view
	disable_on_timeout : bool
		Whether to disable the view on timeout or not

	Methods
	-------
	callback(interaction: discord.Interaction)
		The callback function to execute when a video is selected
	"""

	def __init__(self, videos: list[pytubefix.YouTube], ctx: discord.ApplicationContext, download_file: bool, *items,
				 timeout: float | None = 180, disable_on_timeout: bool = False) -> None:
		super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
		self.add_item(SelectVideo(videos, ctx, download_file))


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
	config: Server = Server.get(server_id=ctx.interaction.guild.id)
	user_playlists = get_user_playlists(ctx.interaction.user.id)
	return ([playlist.playlist.name + " - SERVER" for playlist in config.playlists] +
			[playlist.playlist.name + " - USER" for playlist in user_playlists])


async def get_playlists_songs(ctx: discord.AutocompleteContext):
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
	if ctx.options['playlist'].endswith(" - SERVER"):
		server_playlists = Server.get(server_id=ctx.interaction.guild.id).playlists
		for server_playlist in server_playlists:
			playlist: Playlist = server_playlist.playlist 
			if playlist.name == ctx.options['playlist'][:-9]:
				return [song.song.name for song in playlist.songs]
	elif ctx.options['playlist'].endswith(" - USER"):
		user_playlists = get_user_playlists(ctx.interaction.user.id)
		for user_playlist in user_playlists:
			if user_playlist.playlist.name == ctx.options['playlist'][:-7]:
				return [song.song.name for song in user_playlist.playlist.songs]
	else:
		return []


async def get_queue_songs(ctx: discord.AutocompleteContext):
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
	config: Server = Server.get(server_id=ctx.interaction.guild.id)
	if len(config.queue) < 1:
		return []
	queue_: list[Queue] = config.queue.copy()
	queue_.pop(config.position)
	queue_songs: list[Song] = list(map(lambda queue_elem: queue_elem.song, queue_))
	return [song.name for song in queue_songs]


def get_index_from_title(title: str, list_to_check: list[Song]):
	"""Get the index of a song in a list of songs from its title."""
	for index, song in enumerate(list_to_check):
		if song.name == title:
			return index
	return -1


async def change_song(ctx: discord.ApplicationContext):
	"""Callback function to execute when a song is finished to change the song taking into account the server's
	configuration"""
	server: Server = Server.get(server_id=ctx.guild.id)
	if not server.queue:
		return
	if server.loop_song:
		pass
	elif server.loop_queue or server.position < len(server.queue) - 1:
		server.position = (server.position + 1) % len(server.queue)
		server.save()
	else:
		return
	if server.random and len(server.queue) > 1:
		server.position = random.sample(set(range(0, len(server.queue))) - {server.position}, 1)[0]
		server.save()
	try:
		await play_song(ctx, server.queue[server.position].song.url)
	except Exception as e:
		get_logger("Bot").error(f"Error while playing song: {e}")


async def play_song(ctx: discord.ApplicationContext, url: str):
	"""Play a song from a URL"""
	if ctx.guild.voice_client is None:
		return
	if ctx.guild.voice_client.is_playing():
		ctx.guild.voice_client.stop()
	server: Server = Server.get(server_id=ctx.guild.id)
	loop = asyncio.get_event_loop()
	song = Song.get(url=url)
	song_listen_lount: SongListenCount | None = SongListenCount.get_or_none(song=song)
	if song_listen_lount is not None:
		song_listen_lount.count += 1
		
		song_listen_lount.save()
	else:
		SongListenCount.create(song=song, count=1)
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


class FfmpegFormats(Enum):
	MP3 = ("-codec:a", "libmp3lame")
	FLAC = ("-codec:a", "flac", "-sample_fmt", "s16")
	OGG = ("-codec:a", "libvorbis")
	OPUS = ("-codec:a", "libopus")
	M4A = ("-codec:a", "aac")
	WAV = ("-codec:a", "pcm_s16le")


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