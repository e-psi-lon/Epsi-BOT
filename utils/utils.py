import io
from enum import Enum
import logging
import discord
import os
import random
import ffmpeg
import pydub
import pytube
import asyncio
import discord.ext.pages
from discord.ext import commands
import requests
from .config import Config, Song, Asker, UserPlaylistAccess, format_name
from pytube.exceptions import RegexMatchError as PytubeRegexMatchError

logger = logging.getLogger("__main__")


def download(url: str, file_format: str = "mp3", download_logger=logger):
    """Download a video from a YouTube URL"""
    if not url.startswith("https://youtube.com/watch?v="):
        if os.path.exists(f"cache/{format_name(url.split('/')[-1])}"):
            download_logger.info(f"{url.split('/')[-1]} already in cache as cache/{format_name(url.split('/')[-1])}")
            return f"cache/{format_name(url.split('/')[-1])}"
        r = requests.get(url)
        with open(f"cache/{format_name(url.split('/')[-1])}", "wb") as f:
            f.write(r.content)
        download_logger.info(f"Downloaded {url.split('/')[-1]} to cache/{format_name(url.split('/main')[-1])}")
        return f"cache/{format_name(url.split('/')[-1])}"
    stream = pytube.YouTube(url)
    video_id = stream.video_id
    if stream.age_restricted:
        download_logger.warning(f"Video {stream.title} is age restricted (video id: {video_id})")
        return None
    if os.path.exists(f"cache/{format_name(stream.title)}.{file_format}"):
        download_logger.info(
            f"{stream.title} already in cache as cache/{format_name(stream.title)}.{file_format} "
            f"(video id: {video_id})")
        return f"cache/{format_name(stream.title)}.{file_format}"
    stream = stream.streams.filter(only_audio=True).first()
    stream.download(filename=f"cache\{format_name(stream.title)}.{file_format}")
    download_logger.info(f"Downloaded {stream.title} to cache/{format_name(stream.title)}.{file_format}"
                         f" (video id: {video_id})")
    return f"cache/{format_name(stream.title)}.{file_format}"


class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    ogg = discord.sinks.OGGSink()
    mp4 = discord.sinks.MP4Sink()


async def finished_record_callback(sink, channel: discord.TextChannel):
    mention_strs = []
    audio_segs: list[pydub.AudioSegment] = []
    files: list[discord.File] = []

    longest = pydub.AudioSegment.empty()
    for user_id in sink.audio_data.keys():
        mention_strs.append(f"<@{user_id}>")
    message = await channel.send(
        f"## Recorded {', '.join(mention_strs)}\nProcessing audio" if len(
            mention_strs) > 1 else f"Recorded {mention_strs[0]}\nProcessing audio" if len(
            mention_strs) == 1 else "Recorded no one")

    for user_id, audio in sink.audio_data.items():
        seg = pydub.AudioSegment.from_file(audio.file, format=sink.encoding)

        # Determine the longest audio segment
        if len(seg) > len(longest):
            audio_segs.append(longest)
            longest = seg
        else:
            audio_segs.append(seg)

        audio.file.seek(0)
        files.append(discord.File(audio.file, filename=f"{channel.guild.get_member(user_id).name}.{sink.encoding}"))

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
    ok = False
    for client in bot.voice_clients:
        for guild in client.client.guilds:
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
    def __init__(self, videos: list[pytube.YouTube], ctx, download_file, *args, **kwargs):
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
            stream.download(filename=f"cache/{format_name(stream.title)}.mp3")
            return await interaction.message.edit(
                embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
                file=discord.File(f"cache/{format_name(stream.title)}", filename=f"{format_name(stream.title)}.mp3"),
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
    def __init__(self, videos: list[pytube.YouTube], ctx: discord.ApplicationContext, download_file: bool, *items,
                 timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos, ctx, download_file))


OWNER_ID = 708006478807695450
EMBED_ERROR_QUEUE_EMPTY = discord.Embed(title="Error", description="The queue is empty.", color=0xff0000)
EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST = discord.Embed(title="Error", description="A playlist with this name does "
                                                                                  "not exist. Existing playlists:",
                                                       color=0xff0000)
EMBED_ERROR_BOT_NOT_CONNECTED = discord.Embed(title="Error", description="Bot is not connected to a voice channel.",
                                              color=0xff0000)
EMBED_ERROR_BOT_NOT_PLAYING = discord.Embed(title="Error", description="Bot is not playing anything.", color=0xff0000)
EMBED_ERROR_INDEX_TOO_HIGH = discord.Embed(title="Error", description="The index is too high.", color=0xff0000)
EMBED_ERROR_NAME_TOO_LONG = discord.Embed(title="Error", description="The name is too long.", color=0xff0000)
EMBED_ERROR_NO_RESULTS_FOUND = discord.Embed(title="Error", description="No results found.", color=0xff0000)
EMBED_ERROR_VIDEO_TOO_LONG = discord.Embed(title="Error", description="The video is too long.", color=0xff0000)


async def get_playlists(ctx: discord.AutocompleteContext):
    config = await Config.get_config(ctx.interaction.guild.id, True)
    user_playlists = await UserPlaylistAccess.from_id(ctx.interaction.user.id, True)
    return ([playlist.name + " - SERVER" for playlist in config.playlists] +
            [playlist.name + " - USER" for playlist in user_playlists.playlists])


async def get_playlists_songs(ctx: discord.AutocompleteContext):
    # Si le nom finit par " - SERVER", on cherche dans les playlists du serveur
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
    config = await Config.get_config(ctx.interaction.guild.id, True)
    if len(config.queue) < 1:
        return []
    queue_ = config.queue.copy()
    queue_.pop(config.position)
    return [song.name for song in queue_]


def get_index_from_title(title, list_to_check):
    for index, song in enumerate(list_to_check):
        if song['title'] == title:
            return index
    return -1


async def change_song(ctx: discord.ApplicationContext):
    config = await Config.get_config(ctx.guild.id, False)
    if not config.queue:
        return
    if config.position >= len(config.queue) - 1 and not config.loop_queue:
        config.position = 0
        await config.clear_queue()
    if config.position >= len(config.queue) - 1 and config.loop_queue:
        config.position = -1
    if not config.loop_song:
        if config.random and len(config.queue) > 1:
            config.position = random.choice(list(set(range(0, len(config.queue))) - {config.position}))
        elif len(config.queue) < 1:
            config.position = 0
        else:
            config.position = config.position + 1
    try:
        await play_song(ctx, config.queue[config.position].url)
    except Exception as e:
        logger.error(f"Erreur : {e}")


async def play_song(ctx: discord.ApplicationContext, url: str):
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
        file = download(url)
        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(file, executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
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
        file = download(url)
        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(file, executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
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
    if error is not None and error:
        logger.error("Error:", error)
        await ctx.respond(
            embed=discord.Embed(title="Error", description="An error occurred while playing the song.", color=0xff0000))
    logger.info("Song finished")
    await change_song(ctx)


def convert(audio, file_format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(stream, f"{audio.split('/')[1][:-4]}.{file_format}", format=file_format)
    ffmpeg.run(stream)
    return f"{audio.split('/')[1][:-4]}.{file_format}"


class CustomFormatter(logging.Formatter):
    def __init__(self, source, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source

    format = "[{asctime}] {source} {levelname} : {message} ({path}:{lineno})\033[0m"

    FORMATS = {
        logging.DEBUG: "\033[34m" + format,  # Blue
        logging.INFO: "\033[32m" + format,  # Green
        logging.WARNING: "\033[33m" + format,  # Yellow
        logging.ERROR: "\033[31m" + format,  # Red
        logging.CRITICAL: "\033[41m" + format  # Red
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        path = record.pathname.lower().replace(os.getcwd().lower() + "\\", "").replace("\\", "/").replace("/",
                                                                                                          ".")[:-3]
        path = path.replace(".venv.lib.site-packages.", "libs.")
        formatter = logging.Formatter(log_fmt, "%d/%m/%Y %H:%M:%S", "{", True,
                                      defaults={"source": self.source, "path": path})
        return formatter.format(record)


def get_lyrics(title):
    """Get the lyrics of a song"""
    return title


