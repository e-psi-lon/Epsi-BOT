import discord
from discord.ext import commands
import pytube
import os
import json
from utils import *
from classes import *
import random


class Bot(commands.Bot):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

bot = Bot(intents=discord.Intents.all())
OWNER_ID = 708006478807695450



# Un event qui se déclenche quand le bot rejoins un serveur
@bot.event
async def on_guild_join(guild: discord.Guild):
    create_queue(guild.id)
    # Il faut envoyer un message dans le channel de bienvenue
    # On récupère le channel de bienvenue
    channel = guild.system_channel
    # On vérifie que le channel existe
    if channel is not None:
        # On envoie le message
        await channel.send('Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en test')
    else:
        # On envoie le message dans le premier channel textuel
        await guild.text_channels[0].send('Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en test')

@bot.event
# Quand quelqu'un quitte le salon vocal dans lequel le bot est connecté
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    # On vérifie que le bot est connecté à un salon vocal
    # Vérifier qu'il n'y a qu'une seule personne dans le salon vocal
    if len(after.channel.members) == 1:
        if after.channel.members[0] == bot.user:
            # On déconnecte le bot
            await after.channel.guild.voice_client.disconnect()
            # On supprime la queue
            queue = get_queue(member.guild.id)
            queue['queue'] = []
            queue['channel'] = None
            with open(f'queue/{member.guild.id}.json', 'w') as f:
                json.dump(queue, f, indent=4)
            # On supprime le cache audio
            for file in os.listdir('audio/'):
                os.remove(f'audio/{file}')



@bot.slash_command(name="lyrics", description="Shows the lyrics of the current song")
async def lyrics(ctx: discord.ApplicationContext):
    video = pytube.YouTube(get_queue(ctx.guild.id)['queue'][0]['url'])
    caption = [caption for caption in video.captions][0] if len(video.captions) > 0 else None
    if caption is None:
        embed = discord.Embed(title="Error", description="No lyrics found.", color=0xff0000)
        await ctx.respond(embed=embed)
        return
    embed = discord.Embed(title="Lyrics", description=caption, color=0x00ff00)
    await ctx.respond(embed=embed)
    return

@bot.slash_command(name="play", description="Plays the audio of a YouTube video")
async def play(ctx: discord.ApplicationContext, query: discord.Option(str, "The YouTube audio to play", required=True)):
    voice_client = ctx.voice_client
    await ctx.response.defer()
    if voice_client is None:
        await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        return
    if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/'):
        await start_song(ctx, query)
    else:
        research = pytube.Search(query)
        results: list[pytube.YouTube] = research.results
        if len(results) == 0:
            await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND)
        elif len(results) == 1:
            await start_song(ctx, results[0].watch_url)
        else:
            select = Research(results, ctx=ctx)
            embed = discord.Embed(title="Select an audio to play", description="", color=0x00ff00)
            await ctx.respond(embed=embed, view=select)


playlist = discord.SlashCommandGroup(name="playlist", description="Commands to manage playlists")
@playlist.command(name="create", description="Creates a playlist, from the current queue")
async def create(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist (max 20 chars)", required=True)):
    if len(name) > 20:
        await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        return
    if name in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value=" ")
        await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    if len(queue['queue']) == 0:
        await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        return
    # Une playlist est une liste de dictionnaires, chaque dictionnaire contient l'url de la musique et l'id de la personne qui l'a demandé
    # On utilise les valeurs url et asker contenues dans queue['queue'] pour créer la playlist
    queue['playlist'][name] = [{"title": song["title"], "url": song['url'], "asker": song['asker']} for song in queue['queue']]
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Playlist created", description=f"Created playlist `{name}`", color=0x00ff00)
    await ctx.respond(embed=embed)
    
@playlist.command(name="delete", description="Deletes a playlist")
async def delete(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True)):
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return

@playlist.command(name="add", description="Adds a song to a playlist")
async def add(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True), query: discord.Option(str, "The url of the song", required=True)):
    queue = get_queue(ctx.guild.id)
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    # On regarde ce qu'est query (url ou recherche)
    if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/'):
        url = query
    else:
        research = pytube.Search(query)
        results: list[pytube.YouTube] = research.results
        if len(results) == 0:
            await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND)
            return 
        elif len(results) == 1:
            url =  results[0].watch_url
        else:
            select = Research(results, ctx=ctx, playlist=name)
            embed = discord.Embed(title="Select an audio to play", description="", color=0x00ff00)
            await ctx.respond(embed=embed, view=select)
            return
    queue['playlist'][name].append({"url": url, "asker": ctx.author.id})
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Song added", description=f"Added song `{url}` to playlist `{name}`", color=0x00ff00)
    await ctx.respond(embed=embed)


@playlist.command(name="remove", description="Removes a song from a playlist")
async def remove(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True), index: discord.Option(int, "The index of the song to remove", required=True)):
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    if index > len(get_queue(ctx.guild.id)['playlist'][name]):
        embed = discord.Embed(title="Error", description=f"The index is too high. The playlist has {len(get_queue(ctx.guild.id)['playlist'][name])} songs", color=0xff0000)
        await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    song = queue['playlist'][name].pop(index-1)
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Song removed", description=f"Removed song `{song['url']}` from playlist `{name}`", color=0x00ff00)
    await ctx.respond(embed=embed)


@playlist.command(name="play", description="Plays a playlist")
async def play(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True)):
    await ctx.response.defer()
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    queue['queue'] = queue['playlist'][name]
    queue['index'] = 0
    update_queue(ctx.guild.id, queue)
    queue['index'] = random.randint(0, len(queue['queue'])-1) if queue['random'] else 0
    queue['queue'][queue['index']]['file'], _ = download_audio(queue['queue'][queue['index']]['url'])
    update_queue(ctx.guild.id, queue)
    play_song(ctx, queue['queue'][queue['index']]['file'])
    embed = discord.Embed(title="Playing playlist", description=f"Playing playlist `{name}`", color=0x00ff00)
    await ctx.respond(embed=embed)
    for index, song in enumerate(queue['queue']):
        if index == queue['index']:
            pass
        else:
            song['file'], _ = download_audio(song['url'])
    update_queue(ctx.guild.id, queue)

@playlist.command(name="list", description="Lists all the playlists")
async def list(ctx: discord.ApplicationContext):
    await ctx.response.defer()
    embed = discord.Embed(title="Playlists", description="", color=0x00ff00)
    for name, songs in get_queue(ctx.guild.id)['playlist'].items():
        embed.add_field(name=f"`{name}`", value=f"{len(songs)} songs")
    await ctx.respond(embed=embed)

@playlist.command(name="show", description="Shows a playlist")
async def show(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True)):
    await ctx.response.defer()
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    embed = discord.Embed(title=f"Playlist `{name}`", description="", color=0x00ff00)
    for index, song in enumerate(get_queue(ctx.guild.id)['playlist'][name]):
        embed.add_field(name=f"`{index+1}.`", value=f"[{song['title']}]({song['url']})")
    await ctx.respond(embed=embed)

@playlist.command(name="rename", description="Renames a playlist")
async def rename(ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True), new_name: discord.Option(str, "The new name of the playlist", required=True)):
    if name not in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    if len(new_name) > 20:
        await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        return
    if new_name in get_queue(ctx.guild.id)['playlist'].keys():
        embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
        for name in get_queue(ctx.guild.id)['playlist'].keys():
            embed.add_field(name=f"`{name}`", value="")
        await ctx.respond(embed=embed)
        return
    queue = get_queue(ctx.guild.id)
    queue['playlist'][new_name] = queue['playlist'][name]
    del queue['playlist'][name]
    update_queue(ctx.guild.id, queue)
    embed = discord.Embed(title="Playlist renamed", description=f"Renamed playlist `{name}` to `{new_name}`", color=0x00ff00)
    await ctx.respond(embed=embed)

@bot.slash_command(name="help", description="Shows the help message")
async def help(ctx: discord.ApplicationContext):
    embed = discord.Embed(title="Help", description="The help message", color=0x00ff00)
    group = ""
    for command in bot.application_commands:
        if isinstance(command, discord.SlashCommandGroup):
            group = command.name
            embed.add_field(name=f"__**{group}**__", value=" ", inline=False)
            for subcommand in command.subcommands:
                embed.add_field(name=f"`/{command.name} {subcommand.name}`", value=subcommand.description if subcommand.description is not None else "No description", inline=True)
        elif isinstance(command, discord.SlashCommand):
            if command.cog.__class__.__name__ != group:
                group = command.cog.__class__.__name__
                embed.add_field(name=f"__**{group if group != 'NoneType' else 'Not categorized'}**__", value=" ", inline=False)
            embed.add_field(name=f"`/{command.name}`", value=command.description if command.description is not None else "No description", inline=True)
        else:
            pass
    await ctx.respond(embed=embed)

@bot.slash_command(name="remove_cache", description="Removes the audio cache")
async def remove_cache(ctx: discord.ApplicationContext):
    if ctx.voice_client.is_playing():
        embed = discord.Embed(title="Error", description="The bot is playing a song.", color=0xff0000)
        await ctx.respond(embed=embed)
        return
    for file in os.listdir('audio/'):
        os.remove(f'audio/{file}')
    embed = discord.Embed(title="Cache removed", description="Removed the audio cache.", color=0x00ff00)


def start(instance: Bot):
    # Charger les cogs
    cogs = [
        "state",
        "channel",
        "queue_related",
        "todo",
        "others",
    ]
    for cog in cogs:
        instance.load_extension(f"{cog}")
    # Lancer le bot
    instance.add_application_command(playlist)
    instance.run("MTEyODA3NDQ0Njk4NTQ5ODYyNA.G-kQRY.fuaCtflpY1SrNMJAS2fqixVMmwRUF7m2HRW6tw")


if __name__ == "__main__":
    start(bot)
