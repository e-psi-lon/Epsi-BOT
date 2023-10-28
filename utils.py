import io
from enum import Enum

import discord
import json
import os
import random
import ffmpeg
import pydub
import pytube
import asyncio
import discord.ext.pages
from discord.ext import commands
import requests


def download(url: str, file_format: str = "mp3"):
    """Download a video from a YouTube URL"""
    if not url.startswith("https://youtube.com/watch?v="):
        if os.path.exists(f"cache/{format_name(url.split('/')[-1])}"):
            return f"cache/{format_name(url.split('/')[-1])}"
        r = requests.get(url)
        with open(f"cache/{format_name(url.split('/')[-1])}", "wb") as f:
            f.write(r.content)
        return f"cache/{format_name(url.split('/')[-1])}"
    stream = pytube.YouTube(url).streams.filter(only_audio=True).first()
    if os.path.exists(f"cache/{format_name(stream.title)}.{file_format}"):
        return f"cache/{format_name(stream.title)}.{file_format}"
    stream.download(filename=f"cache/{format_name(stream.title)}.{file_format}")
    return f"cache/{format_name(stream.title)}.{file_format}"


class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    ogg = discord.sinks.OGGSink()
    mp4 = discord.sinks.MP4Sink()


async def finished_record_callback(sink, channel: discord.TextChannel, *args):
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
                queue = get_queue(guild.id)
                queue['queue'] = []
                queue['index'] = 0
                update_queue(guild.id, queue)
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
        await interaction.message.edit(
            embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}",
                                color=0x00ff00), view=None)
        queue = get_queue(interaction.guild.id)
        if self.download:
            stream = pytube.YouTube(self.values[0]).streams.filter(only_audio=True).first()
            if pytube.YouTube(self.values[0]).length > 12000:
                return await interaction.message.edit(embed=discord.Embed(title="Error",
                                                                          description=f"The video [{pytube.YouTube(self.values[0]).title}]({self.values[0]}) is too long",
                                                                          color=0xff0000))
            stream.download(filename=f"cache/{self.options[0].label}.mp3")
            return await interaction.message.edit(
                embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
                file=discord.File(f"cache{self.options[0].label}", filename=f"{self.options[0].label}.mp3"), view=None)
        if not queue['queue']:
            queue['index'] = 0
            queue['queue'].append({'title': self.options[0].label, 'url': self.values[0], 'asker': interaction.user.id})
            update_queue(interaction.guild.id, queue)
        else:
            queue['queue'].append({'title': self.options[0].label, 'url': self.values[0], 'asker': interaction.user.id})
            update_queue(interaction.guild.id, queue)
        if interaction.guild.voice_client is None:
            await interaction.user.voice.channel.connect()
        if not interaction.guild.voice_client.is_playing():
            await interaction.message.edit(embed=discord.Embed(title="Play",
                                                               description=f"Playing song [{self.options[0].label}]({self.values[0]})",
                                                               color=0x00ff00))
            await play_song(self.ctx, queue['queue'][queue['index']]['url'])
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue",
                                                               description=f"Song [{pytube.YouTube(self.values[0]).title}]({self.values[0]}) added to queue.",
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
    return [name for name in get_queue(ctx.interaction.guild.id)['playlist'].keys()]


async def get_playlists_songs(ctx: discord.AutocompleteContext):
    return [song['title'] for song in get_queue(ctx.interaction.guild.id)['playlist'][ctx.options['name']]]


async def get_queue_songs(ctx: discord.AutocompleteContext):
    queue = get_queue(ctx.interaction.guild.id)
    if len(queue['queue']) == 0:
        return []
    queue['queue'].pop(queue['index'])
    return [song['title'] for song in queue['queue']]


def format_name(name: str):
    """Replace |, /, backslash, <, >, :, *, ?, ", and ' with a character with their unicode"""
    return name.replace("|", "u01C0") \
        .replace("/", "u2215") \
        .replace("\\", "u2216") \
        .replace("<", "u003C") \
        .replace(">", "u003E") \
        .replace(":", "u02D0") \
        .replace("*", "u2217") \
        .replace("?", "u003F") \
        .replace('"', "u0022") \
        .replace("'", "u0027")


def update_queue(guild_id, queue):
    with open(f'queue/{guild_id}.json', 'w') as f:
        json.dump(queue, f, indent=4)


def get_index_from_title(title, list_to_check):
    for index, song in enumerate(list_to_check):
        if song['title'] == title:
            return index
    return -1


async def change_song(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild.id)
    if not queue['queue']:
        return
    if queue['index'] >= len(queue['queue']) - 1 and not queue['loop-queue']:
        queue['index'] = 0
        queue['queue'] = []
        return update_queue(ctx.guild.id, queue)
    if queue['index'] >= len(queue['queue']) - 1 and queue['loop-queue']:
        queue['index'] = -1
    if not queue['loop-song']:
        if queue['random'] and len(queue['queue']) > 1:
            queue['index'] = random.choice(list(set(range(0, len(queue['queue']))) - {queue['index']}))
        elif len(queue['queue']) < 1:
            queue['index'] = 0
        else:
            queue['index'] += 1
    update_queue(ctx.guild.id, queue)
    try:
        await play_song(ctx, queue['queue'][queue['index']]['url'])
    except Exception as e:
        print(f"Erreur : {e}")


async def play_song(ctx: discord.ApplicationContext, url: str):
    if ctx.guild.voice_client is None:
        return
    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    try:
        video = pytube.YouTube(url)
        if video.length > 12000:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"The video [{video.title}]({url}) is too long",
                                    color=0xff0000))
        player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(download(url), executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
        try:
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
        except:
            while ctx.guild.voice_client.is_playing():
                await asyncio.sleep(0.1)
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
    except:
        player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(download(url), executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
        ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                    wait_finish=True)


async def on_play_song_finished(ctx: discord.ApplicationContext, error=None):
    if error is not None and error:
        print("Error:", error)
        await ctx.respond(
            embed=discord.Embed(title="Error", description="An error occured while playing the song.", color=0xff0000))
    await change_song(ctx)


def create_queue(guild_id):
    if not os.path.exists(f'queue/{guild_id}.json'):
        with open(f'queue/{guild_id}.json', 'w') as f:
            json.dump(
                {"channel": None, "loop-song": False, "loop-queue": False, "index": 0, "queue": [], "playlist": {}}, f,
                indent=4)


def get_queue(guild_id) -> dict:
    try:
        return json.load(open(f'queue/{guild_id}.json', 'r'))
    except FileNotFoundError:
        create_queue(guild_id)
        return json.load(open(f'queue/{guild_id}.json', 'r'))


def convert(audio, file_format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(stream, f"{audio.split('/')[1][:-4]}.{file_format}", format=file_format)
    ffmpeg.run(stream)
    return f"{audio.split('/')[1][:-4]}.{file_format}"
