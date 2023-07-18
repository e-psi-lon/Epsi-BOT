import discord
import json
import os
import pytube
import random
import ffmpeg
import asyncio
import io
from typing import BinaryIO

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


def link_to_audio(url:str) -> io.BufferedIOBase:
    stream = pytube.YouTube(url).streams.filter(only_audio=True).first()
    if stream is None:
        return None
    # on limite la taille du fichier à 80 Mo
    if stream.filesize > 80 * 1024 * 1024:
        return None
    buffer = io.BytesIO()
    stream.stream_to_buffer(buffer)
    buffer.seek(0)
    return buffer


async def change_song(ctx: discord.ApplicationContext):
    queue = get_queue(ctx.guild.id)
    if queue['queue'] == []:
        return
    if queue['index'] >= len(queue['queue']) and not queue['loop_queue']:
        queue['index'] = 0
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        return
    if queue['index'] >= len(queue['queue']) and queue['loop_queue']:
        queue['index'] = -1
    if not queue['loop_song']:
        queue['index'] += 1
    update_queue(ctx.guild.id, queue)
    try:
        play_song(ctx, link_to_audio(queue['queue'][queue['index']]['url']))
    except Exception as e:
        ctx.respond(embed=discord.Embed(title="Error", description="Error while playing song. Error: " + str(e), color=0xff0000))
    await asyncio.sleep(1)
    



def play_song(ctx: discord.ApplicationContext, buffer: io.BufferedIOBase):
    if ctx.guild.voice_client is None:
        return
    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    ctx.guild.voice_client.play(discord.FFmpegPCMAudio(buffer), after=lambda e: ctx.respond("Error while playing song.") if e else change_song(ctx))


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
