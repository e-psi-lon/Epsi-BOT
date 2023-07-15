import discord
import json
import os
import pytube
import random
import ffmpeg
import asyncio
import io

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


def get_index_from_title(title, guild_id, list):
    for index, song in enumerate(list):
        if song['title'] == title:
            return index
    return -1


async def change_song(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild.id)
    if queue['loop-song']:
        play_song(ctx, queue['queue'][queue['index']]['file'])
    elif queue['loop-queue']:
        if queue['random']:
            previous_index = queue['index']
            while queue['index'] == previous_index and len(queue['queue']) > 1:
                queue['index'] = get_index_from_title(random.choice(list(set(range(0,len(queue['queue']))) - set([queue['index']]))) , queue['queue'])
        else:
            queue['index'] += 1
        if queue['index'] >= len(queue['queue']):
            queue['index'] = 0
        update_queue(ctx.guild.id, queue)
        play_song(ctx, queue['queue'][queue['index']]['file'])
    else:
        if queue['random']:
            previous_index = queue['index']
            while queue['index'] == previous_index and len(queue['queue']) > 1:
                queue['index'] = get_index_from_title(random.choice(list(set(range(0,len(queue['queue']))) - set([queue['index']]))) , queue['queue'])
        else:
            queue['index'] += 1
        if queue['index'] >= len(queue['queue']):
            queue['index'] = 0
            update_queue(ctx.guild.id, queue)
            return
        update_queue(ctx.guild.id, queue)
        if len(queue['queue']) > 0:
            play_song(ctx, queue['queue'][queue['index']]['file'])
        else:
            ctx.voice_client.stop()
            for file in os.listdir('audio/'):
                os.remove(f'audio/{file}')


def download_audio(url, guild_id: int | None = None):
    video = pytube.YouTube(url)
    if video.length > 3600:
        return -1, None
    if guild_id is not None:
        queue = get_queue(guild_id)
        # On modifie directement la valeur file de le ou les element de la queue qui possède l'url de la vidéo (si il(ss) existe(nt)
        for element in queue['queue']:
            if element['url'] == url:
                element['file'] = f'audio/{format_name(video.title)}.ogg'
        update_queue(guild_id, queue)
    audio_stream = video.streams.filter(only_audio=True).first()
    if os.path.exists(f'{format_name(video.title)}.ogg'):
        return f'{format_name(video.title)}.ogg', video
    else:
        audio_stream.download(output_path='audio/', filename=f'{format_name(video.title)}.ogg')
        while audio_stream.filesize != os.path.getsize(f'audio/{format_name(video.title)}.ogg'):
            asyncio.sleep(0.1)
        return f'audio/{format_name(video.title)}.ogg', video


def play_song(ctx: discord.ApplicationContext, file: str):
    if not os.path.exists(file):
        queue = get_queue(ctx.guild.id)
        file, _ = download_audio(queue['queue'][queue['index']]['url'])
        if file == -1:
            ctx.message.reply(embed=EMBED_ERROR_VIDEO_TOO_LONG, delete_after=30)
            return
    voice_client = ctx.voice_client
    source = discord.FFmpegPCMAudio(file)
    voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else asyncio.run(change_song(ctx)))


def create_queue(guild_id):
    if not os.path.exists(f'queue/{guild_id}.json'):
        with open(f'queue/{guild_id}.json', 'w') as f:
            json.dump(
                {"channel": None, "loop-song": False, "loop-queue": False, "index": 0, "queue": [], "playlist": {}}, f,
                indent=4)


def get_queue(guild_id):
    return json.load(open(f'queue/{guild_id}.json', 'r'))


async def start_song(ctx: discord.ApplicationContext, url: str, message: discord.Message | None = None):
    # Si il y a déjà une musique en cours de lecture
    file, video = download_audio(url)
    if file == -1:
        await ctx.respond(embed=EMBED_ERROR_VIDEO_TOO_LONG, delete_after=30)
        return
    if ctx.voice_client.is_playing():
        queue = get_queue(ctx.guild.id)
        queue['queue'].append({"file": file, "title": format_name(video.title), "url": url, "asker": ctx.author.id})
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Added to queue", description=f"Added song `{video.title}` to the queue",
                              color=0x00ff00)
        if message is not None:
            await message.edit(embed=embed, view=None)
        else:
            await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    queue['queue'].append({"file": file, "title": format_name(video.title), "url": url, "asker": ctx.author.id})
    play_song(ctx, file)
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Playing", description=f"Playing song `{video.title}`", color=0x00ff00)
    if message is not None:
        await message.edit(embed=embed, view=None)
    else:
        await ctx.respond(embed=embed)


def convert(audio, file_format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(audio[:4], stream, format=file_format)
    ffmpeg.run(stream)
    return f'{audio}.{file_format}'
