import discord
import json
import os
import pytube
import random
import ffmpeg

EMBED_ERROR_QUEUE_EMPTY = discord.Embed(title="Error", description="The queue is empty.", color=0xff0000)
EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST = discord.Embed(title="Error", description="A playlist with this name does not exist. Existing playlists:", color=0xff0000)
EMBED_ERROR_BOT_NOT_CONNECTED = discord.Embed(title="Error", description="Bot is not connected to a voice channel.", color=0xff0000)
EMBED_ERROR_BOT_NOT_PLAYING = discord.Embed(title="Error", description="Bot is not playing anything.", color=0xff0000)
EMBED_ERROR_INDEX_TOO_HIGH = discord.Embed(title="Error", description="The index is too high.", color=0xff0000)
EMBED_ERROR_NAME_TOO_LONG = discord.Embed(title="Error", description="The name is too long.", color=0xff0000)
EMBED_ERROR_NO_RESULTS_FOUND = discord.Embed(title="Error", description="No results found.", color=0xff0000)


def format_name(name: str):
    """Replace |, /, \, <, >, :, *, ?, ", and ' with a caracter with their unicode"""
    return name.replace("|", "u01C0")\
        .replace("/", "u2215")\
        .replace("\\", "u2216")\
        .replace("<", "u003C")\
        .replace(">", "u003E")\
        .replace(":", "u02D0")\
        .replace("*", "u2217")\
        .replace("?", "u003F")\
        .replace('"', "u0022")\
        .replace("'", "u0027")

def update_queue(guild_id, queue):
    with open(f'queue/{guild_id}.json', 'w') as f:
        json.dump(queue, f, indent=4)

def change_song(ctx: discord.ApplicationContext, how_much: int | None = None):
    if how_much is not None:
        queue = get_queue(ctx.guild.id)
        if queue['loop-queue']:
            queue['loop-queue'] = False
        if queue['loop-song']:
            queue['loop-song'] = False
        queue['index'] += how_much
        if queue['index'] >= len(queue['queue']):
            queue['index'] = 0
        elif queue['index'] < 0:
            queue['index'] = len(queue['queue'])-1
        update_queue(ctx.guild.id, queue)
        play_song(ctx, queue['queue'][queue['index']]['file'])
        return
    queue = get_queue(ctx.guild.id)
    if queue['loop-song']:
        play_song(ctx, queue['queue'][queue['index']]['file']) 
    elif queue['loop-queue']:
        if queue['random']:
            previous_index = queue['index']
            while queue['index'] == previous_index and len(queue['queue']) > 1:
                queue['index'] = random.randint(0, len(queue['queue'])-1) if len(queue['queue']) > 1 else 0
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
                queue['index'] = random.randint(0, len(queue['queue'])-1) if len(queue['queue']) > 1 else 0
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

def download_audio(url):
    video = pytube.YouTube(url)
    audio_stream = video.streams.filter(only_audio=True).first()
    if os.path.exists(f'{format_name(video.title)}.ogg'):
        print("Already downloaded")
        return f'{format_name(video.title)}.ogg', video
    else:
        "Downloading"
        audio_stream.download(output_path='audio/', filename=f'{format_name(video.title)}.ogg')
        while audio_stream.filesize != os.path.getsize(f'audio/{format_name(video.title)}.ogg'):
            pass
        return f'audio/{format_name(video.title)}.ogg', video
    

def play_song(ctx: discord.ApplicationContext, file: str):
    voice_client = ctx.voice_client
    source = discord.FFmpegPCMAudio(file)
    voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else change_song(ctx))

def create_queue(guild_id):
    if not os.path.exists(f'queue/{guild_id}.json'):
        with open(f'queue/{guild_id}.json', 'w') as f:
            json.dump({"channel": None, "loop-song": False , "loop-queue": False , "index": 0, "queue": [], "playlist":{}}, f, indent=4)

def get_queue(guild_id):
    return json.load(open(f'queue/{guild_id}.json', 'r'))

async def start_song(ctx: discord.ApplicationContext, url: str):
    # Si il y a déjà une musique en cours de lecture
    file, video = download_audio(url)
    if ctx.voice_client.is_playing():
        queue = get_queue(ctx.guild.id)
        queue['queue'].append({"file": file, "title": format_name(video.title), "url": url, "asker": ctx.author.id})
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Added to queue", description=f"Added song `{video.title}` to the queue", color=0x00ff00)
        await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    queue['queue'].append({"file": file, "title": format_name(video.title), "url": url, "asker": ctx.author.id})
    play_song(ctx, file)
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Playing", description=f"Playing song `{video.title}`", color=0x00ff00)
    await ctx.respond(embed=embed)


def convert(audio, format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg
    ffmpeg.run(stream)
    return f'{audio}.{format}'