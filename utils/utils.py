import asyncio
import io
import logging
import os
import random
from enum import Enum
from typing import Optional, Union

import discord
import discord.ext.pages
import ffmpeg  # type: ignore
import pydub  # type: ignore
import pytube  # type: ignore
from aiocache import Cache  # type: ignore
from discord.ext import commands
from pytube.exceptions import RegexMatchError as PytubeRegexMatchError  # type: ignore

pydub.AudioSegment.converter = "./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"

from .config import Config, Song, Asker, UserPlaylistAccess, format_name
from .async_ import AsyncRequests
from .constants import EMBED_ERROR_BOT_NOT_CONNECTED

logger = logging.getLogger("__main__")

cache = Cache()


async def to_cache(url: str) -> io.BytesIO:
    """
    Download a video from a YouTube (or other) URL and save it in the cache, 
    or get it from the cache if it already exists.\n
    Then return the video as a BytesIO object.

    Parameters
    ----------
    url : str
        The URL of the video to download

    Returns
    -------
    io.BytesIO
        The downloaded video
    """
    if await cache.exists(url):
        return await cache.get(url)
    buffer = io.BytesIO()
    if not url.startswith("https://youtube.com/watch?v="):
        r: bytes = await AsyncRequests.get(url, return_type="content")
        buffer.write(r)
    else:
        stream = pytube.YouTube(url)
        stream = stream.streams.filter(only_audio=True).first()
        buffer = io.BytesIO()
        stream.stream_to_buffer(buffer)
    buffer.seek(0)
    await cache.set(url, buffer, ttl=3600)
    return buffer


async def update_ttl(key: str, new_ttl: int):
    """Update the ttl of a key in the cache"""
    buffer = await cache.get(key)
    await cache.set(key, buffer, ttl=new_ttl)


async def reset_ttl(key: str):
    """Reset the ttl of a key in the cache"""
    buffer = await cache.get(key)
    await cache.set(key, buffer, ttl=3600)


async def download(url: str, download_logger: logging.Logger = logger) -> Optional[Union[io.BytesIO, str]]:
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
    if not url.startswith("https://youtube.com/watch?v="):
        buffer: io.BytesIO = await to_cache(url)
        download_logger.info(f"Downloaded {url.split('/')[-1]}")
        return buffer
    else:
        stream = pytube.YouTube(url)
        video_id = stream.video_id
        if stream.age_restricted:
            download_logger.warning(f"Video {stream.title} is age restricted (video id: {video_id})")
            return None
        buffer = await to_cache(url)
        logger.info(f"Downloaded {stream.title}")
        return buffer


class Sinks(Enum):
    """Enum for the different types of audio sinks"""
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    ogg = discord.sinks.OGGSink()
    mp4 = discord.sinks.MP4Sink()


async def finished_record_callback(sink: discord.sinks.Sink, channel: discord.TextChannel):
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


async def disconnect_from_channel(state: discord.VoiceState, bot: commands.Bot):
    """Callback function to execute when the bot has to disconnect from a voice channel"""
    ok = False
    for client in bot.voice_clients:
        for guild in client.client.guilds:
            if state.channel is None:
                return await client.disconnect(force=True)
            if guild.id == state.channel.guild.id:
                await client.disconnect(force=True)
                config = await Config.get_config(guild.id, False)
                await config.clear_queue()
                config.position = 0
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
    videos : list[pytube.YouTube]
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

    def __init__(self, videos: list[pytube.YouTube], ctx: discord.ApplicationContext, download_file: bool, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.download = download_file
        options = []
        for video in videos:
            if video in options:
                continue
            options.append(discord.SelectOption(label=video.title, value=video.watch_url))
        self.options = options

    async def callback(self, interaction: discord.Interaction):
        # Si l'utilisateur à l'origine du select n'est pas l'utilisateur à l'origine de l'interaction, on ignore
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("You are not the author of the command.", ephemeral=True)
        await interaction.message.edit(
            embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}",
                                color=0x00ff00), view=None)
        config = await Config.get_config(interaction.guild.id, False)
        if self.download:
            stream = pytube.YouTube(self.values[0]).streams.filter(only_audio=True).first()
            if pytube.YouTube(self.values[0]).length > 12000:
                return await interaction.message.edit(embed=discord.Embed(title="Error",
                                                                          description=f"The video "
                                                                                      f"""[{pytube.YouTube(self.values[0])
                                                                          .title}]({self.values[0]}) is too long""",
                                                                          color=0xff0000))
            buffer = io.BytesIO()
            stream.stream_to_buffer(buffer)
            buffer.seek(0)
            return await interaction.message.edit(
                embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
                file=discord.File(buffer, filename=f"{format_name(stream.title)}.mp3"),
                view=None)
        if not config.queue:
            config.position = 0
            await config.add_to_queue(await Song.create(pytube.YouTube(self.values[0]).title, self.values[0],
                                                        await Asker.from_id(interaction.user.id)))
        else:
            await config.add_to_queue(await Song.create(pytube.YouTube(self.values[0]).title, self.values[0],
                                                        await Asker.from_id(interaction.user.id)))
        if interaction.guild.voice_client is None:
            return await interaction.message.edit(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not interaction.guild.voice_client.is_playing():
            await interaction.message.edit(embed=discord.Embed(title="Play",
                                                               description=f"Playing song "
                                                                           f"[{pytube.YouTube(self.values[0]).title}]"
                                                                           f"({self.values[0]})",
                                                               color=0x00ff00))
            await play_song(self.ctx, config.queue[config.position].url)
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue",
                                                               description=f"Song "
                                                                           f"[{pytube.YouTube(self.values[0]).title}]"
                                                                           f"({self.values[0]}) added to queue.",
                                                               color=0x00ff00))


class Research(discord.ui.View):
    """
    View to search for a video to play using a select menu

    Parameters
    ----------
    videos : list[pytube.YouTube]
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

    def __init__(self, videos: list[pytube.YouTube], ctx: discord.ApplicationContext, download_file: bool, *items,
                 timeout: float | None = 180, disable_on_timeout: bool = False):
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
    config = await Config.get_config(ctx.interaction.guild.id, True)
    user_playlists = await UserPlaylistAccess.from_id(ctx.interaction.user.id, True)
    return ([playlist.name + " - SERVER" for playlist in config.playlists] +
            [playlist.name + " - USER" for playlist in user_playlists.playlists])


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
        config = await Config.get_config(ctx.interaction.guild.id, True)
        playlist = await config.get_playlist(ctx.options['playlist'][:-8])
        return [song.name for song in playlist.songs]
    elif ctx.options['playlist'].endswith(" - USER"):
        user_playlists = await UserPlaylistAccess.from_id(ctx.interaction.user.id, True)
        playlist = await user_playlists.get_playlist(ctx.options['playlist'][:-6])
        return [song.name for song in playlist.songs]
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
    config = await Config.get_config(ctx.interaction.guild.id, True)
    if len(config.queue) < 1:
        return []
    queue_ = config.queue.copy()
    queue_.pop(config.position)
    return [song.name for song in queue_]


def get_index_from_title(title: str, list_to_check: list[Song]):
    """Get the index of a song in a list of songs from its title."""
    for index, song in enumerate(list_to_check):
        if song.title == title:
            return index
    return -1


async def change_song(ctx: discord.ApplicationContext):
    """Callback function to execute when a song is finished to change the song taking into account the server's
    configuration"""
    if not (config := await Config.get_config(ctx.guild.id, False)).queue:
        return
    if config.position >= len(config.queue) - 1 and not (config.loop_queue and config.loop_song):
        config.position = 0
        await config.clear_queue()
    if config.position >= len(config.queue) - 1 and config.loop_queue and not config.loop_song:
        config.position = -1
    if config.position >= len(config.queue) - 1 and not config.loop_queue:
        return
    if not config.loop_song:
        if config.random and len(config.queue) > 1:
            config.position = random.choice(list(set(range(0, len(config.queue))) - set([config.position])))
        elif len(config.queue) < 1:
            config.position = 0
        else:
            config.position += 1
    try:
        await play_song(ctx, config.queue[config.position].url)
    except Exception as e:
        logger.error(f"Error while playing song: {e}")


async def play_song(ctx: discord.ApplicationContext, url: str):
    """Play a song from a URL"""
    if ctx.guild.voice_client is None:
        return
    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    config = await Config.get_config(ctx.guild.id, True)
    try:
        video = pytube.YouTube(url)
        if video.age_restricted:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"The [video]({url}) is age restricted",
                                    color=0xff0000))
        if video.length > 12000:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"The video [{video.title}]({url}) is too long",
                                    color=0xff0000))
        file = await download(url, download_logger=logging.getLogger("Audio-Downloader"))
        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(file, executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg", pipe=True),
            config.volume / 100)
        try:
            logger.info(f"Playing song {video.title}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)

        except discord.errors.ClientException:
            while ctx.guild.voice_client.is_playing():
                await asyncio.sleep(0.1)
            logger.info(f"Playing song {video.title}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
    except PytubeRegexMatchError:
        file = await download(url, download_logger=logging.getLogger("Audio-Downloader"))
        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(file, executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg", pipe=True),
            config.volume / 100)
        try:
            logger.info(f"Playing song {url}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
        except discord.errors.ClientException:
            try:
                await ctx.guild.voice_client.disconnect(force=True)
            except discord.errors.ClientException:
                pass
            await ctx.author.voice.channel.connect()
            logger.info(f"Playing song {url}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)


async def on_play_song_finished(ctx: discord.ApplicationContext, error=None):
    """Callback function to execute when a song is finished"""
    if error is not None and error:
        logger.error("Error:", error)
        await ctx.respond(
            embed=discord.Embed(title="Error", description="An error occurred while playing the song.", color=0xff0000))
    logger.info("Song finished")
    await change_song(ctx)


def convert(audio: io.BytesIO, file_format: str) -> io.BytesIO:
    """Convert an audio file to another format"""
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(stream, f"{audio.split('/')[1][:-4]}.{file_format}", format=file_format)
    ffmpeg.run(stream)
    return io.BytesIO(open(f"{audio.split('/')[1][:-4]}.{file_format}", "rb").read())


class CustomFormatter(logging.Formatter):
    """Custom formatter for the bot and the panel's logs"""

    def __init__(self, source: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source

    format_ = "[{asctime}] {source} {levelname} : {message} ({path}:{lineno})\033[0m"

    FORMATS = {
        logging.DEBUG: "\033[34m" + format_,  # Blue
        logging.INFO: "\033[32m" + format_,  # Green
        logging.WARNING: "\033[33m" + format_,  # Yellow
        logging.ERROR: "\033[31m" + format_,  # Red
        logging.CRITICAL: "\033[41m" + format_  # Red
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        path = record.pathname.lower().replace(os.getcwd().lower() + "\\", "").replace("\\", "/").replace("/",
                                                                                                          ".")[:-3]
        path = path.replace(".venv.lib.site-packages.", "libs.")
        formatter = logging.Formatter(log_fmt, "%d/%m/%Y %H:%M:%S", "{", True,
                                      defaults={"source": self.source, "path": path})
        return formatter.format(record)


def get_lyrics(title: str):
    """Get the lyrics of a song"""
    return title
