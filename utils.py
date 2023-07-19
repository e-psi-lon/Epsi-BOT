import discord
import json
import os
import random
import ffmpeg
import pytube
from discord.ui.item import Item
import youtube_dl
import asyncio



ffmpeg_options = {"options": "-vn"}
ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": (
        "0.0.0.0"
    ),  # Bind to ipv4 since ipv6 addresses cause issues at certain times
}


ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source: discord.AudioSource, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream)
        )

        if "entries" in data:
            # Takes the first item from a playlist
            data = data["entries"][0]

        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class SelectVideo(discord.ui.Select):
    def __init__(self, videos:list[pytube.YouTube], ctx, download, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.download = download
        options = []
        for video in videos:
            if video in options:
                continue
            options.append(discord.SelectOption(label=video.title, value=video.watch_url))
        self.options = options
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.message.edit(embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}", color=0x00ff00), view=None)
        queue = get_queue(interaction.guild.id)
        if self.download:
            stream = pytube.YouTube(self.values[0]).streams.filter(only_audio=True).first()
            stream.download(filename=f"cache/{self.options[0].label}.mp3")
            await interaction.message.edit(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00), file=discord.File(f"cache{self.options[0].label}", filename=f"{self.options[0].label}.mp3"), view=None)
            return
        if queue['queue'] == []:
            queue['index'] = 0
            queue['queue'].append({'title': self.options[0].label, 'url': self.values[0], 'asker': interaction.user.id})
            update_queue(interaction.guild.id, queue)
        else:
            queue['queue'].append({'title': self.options[0].label, 'url': self.values[0], 'asker': interaction.user.id})
            update_queue(interaction.guild.id, queue)
        if interaction.guild.voice_client is None:
            await interaction.user.voice.channel.connect()
        if not interaction.guild.voice_client.is_playing():
            await interaction.message.edit(embed=discord.Embed(title="Play", description=f"Playing song [{self.options[0].label}]({self.values[0]})", color=0x00ff00))
            await play_song(self.ctx, queue['queue'][queue['index']]['url'])
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue", description=f"Song {self.values[0]} added to queue.", color=0x00ff00))

class Research(discord.ui.View):
    def __init__(self, videos:list[pytube.YouTube], ctx:discord.ApplicationContext, download: bool, *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos, ctx, download))

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
    """Replace |, /, \, <, >, :, *, ?, ", and ' with a caracter with their unicode"""
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


def get_index_from_title(title, list):
    for index, song in enumerate(list):
        if song['title'] == title:
            return index
    return -1


def change_song(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild.id)
    if queue['queue'] == []:
        return
    if queue['index'] >= len(queue['queue']) and not queue['loop-queue']:
        queue['index'] = 0
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        return
    if queue['index'] >= len(queue['queue']) and queue['loop-queue']:
        queue['index'] = -1
    if not queue['loop-song']:
        if queue['random'] and len(queue['queue']) > 1:
            queue['index'] = random.choice(list(set(range(0,len(queue['queue']))) - set([queue['index']])))
        elif len(queue['queue']) < 1:
            queue['index'] = 0
        else:
            queue['index'] += 1
    update_queue(ctx.guild.id, queue)
    try:
        asyncio.run(play_song(ctx, queue['queue'][queue['index']]['url']))
    except Exception as e:
        print(e)
    



async def play_song(ctx: discord.ApplicationContext, url: str):
    if ctx.guild.voice_client is None:
        return
    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    player = await YTDLSource.from_url(url, loop=ctx.bot.loop, stream=True)
    ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)))

async def on_play_song_finished(ctx: discord.ApplicationContext, error = None):
    print("Playback finished!")
    if error is not None and error:
        print("Error:", error)
        await ctx.respond(embed=discord.Embed(title="Error", description="An error occured while playing the song.", color=0xff0000))
    else:
        print("No error. Playback successful.")
    change_song(ctx)

def create_queue(guild_id):
    if not os.path.exists(f'queue/{guild_id}.json'):
        with open(f'queue/{guild_id}.json', 'w') as f:
            json.dump(
                {"channel": None, "loop-song": False, "loop-queue": False, "index": 0, "queue": [], "playlist": {}}, f,
                indent=4)


def get_queue(guild_id):
    return json.load(open(f'queue/{guild_id}.json', 'r'))


def convert(audio, file_format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(audio[:4], stream, format=file_format)
    ffmpeg.run(stream)
    return f'{audio}.{file_format}'
