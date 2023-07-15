import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils import *
from classes import Research
import pytube
import threading




class Playlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

    @playlist.command(name="create", description="Creates a playlist, from the current queue")
    async def create(self, ctx: discord.ApplicationContext,
                    name: discord.Option(str, "The name of the playlist (max 20 chars)", required=True)):
        if len(name) > 20:
            await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG, delete_after=30)
            return
        if name in get_queue(ctx.guild.id)['playlist'].keys():
            embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
            for name in get_queue(ctx.guild.id)['playlist'].keys():
                embed.add_field(name=f"`{name}`", value=" ")
            await ctx.respond(embed=embed, delete_after=30)
            return
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY, delete_after=30)
            return
        # Une playlist est une liste de dictionnaires, chaque dictionnaire contient l'url de la musique et l'id de la
        # personne qui l'a demandé On utilise les valeurs url et asker contenues dans queue['queue'] pour créer la playlist
        queue['playlist'][name] = [{"title": song["title"], "url": song['url'], "asker": song['asker']} for song in
                                queue['queue']]
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Playlist created", description=f"Created playlist `{name}`", color=0x00ff00)
        await ctx.respond(embed=embed)


    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        if name not in get_queue(ctx.guild.id)['playlist'].keys():
            embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
            for name in get_queue(ctx.guild.id)['playlist'].keys():
                embed.add_field(name=f"`{name}`", value="")
            await ctx.respond(embed=embed, delete_after=30)
            return


    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                query: discord.Option(str, "The url of the song", required=True)):
        queue = get_queue(ctx.guild.id)
        if name not in get_queue(ctx.guild.id)['playlist'].keys():
            embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
            for name in get_queue(ctx.guild.id)['playlist'].keys():
                embed.add_field(name=f"`{name}`", value="")
            await ctx.respond(embed=embed, delete_after=30)
            return
        # On regarde ce qu'est query (url ou recherche)
        if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/') or query.startswith('https://youtube.com/watch?v='):
            url = query
        else:
            research = pytube.Search(query)
            results: list[pytube.YouTube] = research.results
            if len(results) == 0:
                await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND, delete_after=30)
                return
            elif len(results) == 1:
                url = results[0].watch_url
            else:
                select = Research(results, ctx=ctx, playlist=name)
                embed = discord.Embed(title="Select an audio to play", description="", color=0x00ff00)
                await ctx.respond(embed=embed, view=select)
                return
        queue['playlist'][name].append({"url": url, "asker": ctx.author.id, "title": pytube.YouTube(url).title})
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Song added", description=f"Added song `{pytube.YouTube(url).title}` to playlist `{name}`", color=0x00ff00)
        await ctx.respond(embed=embed)


    @playlist.command(name="remove", description="Removes a song from a playlist")
    async def remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    song: discord.Option(str, "The name of the song", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))):
        if name not in get_queue(ctx.guild.id)['playlist'].keys():
            embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
            for name in get_queue(ctx.guild.id)['playlist'].keys():
                embed.add_field(name=f"`{name}`", value="")
            await ctx.respond(embed=embed)
            return
        if song not in [song['title'] for song in get_queue(ctx.guild.id)['playlist'][name]]:
            embed = discord.Embed(title="Error",
                                description=f"The index is too high. The playlist has "
                                        f"{len(get_queue(ctx.guild.id)['playlist'][name])} songs",
                                color=0xff0000)
            await ctx.respond(embed=embed)
            return
        queue = get_queue(ctx.guild.id)
        queue['playlist'][name].pop(get_index_from_title(song, ctx.guild.id, queue['playlist'][name]))
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Song removed", description=f"Removed song `{song['url']}` from playlist `{name}`",
                            color=0x00ff00)
        await ctx.respond(embed=embed)


    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        await ctx.response.defer()
        if ctx.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
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
        queue['index'] = random.randint(0, len(queue['queue']) - 1) if queue['random'] else 0
        video, _ = download_audio(queue['queue'][queue['index']]['url'])
        if video == -1:
            await ctx.respond(embed=EMBED_ERROR_VIDEO_TOO_LONG, delete_after=30)
            return
        queue['queue'][queue['index']]['file'] = video
        update_queue(ctx.guild.id, queue)
        play_song(ctx, queue['queue'][queue['index']]['file'])
        embed = discord.Embed(title="Playing playlist", description=f"Playing playlist `{name}` (continue downloading songs in the background, please don't execute a command)", color=0x00ff00)
        response = await ctx.respond(embed=embed)
        for index, song in enumerate(queue['queue']):
            if index == queue['index']:
                pass
            else:
                while threading.active_count() > 7:
                    await asyncio.sleep(1)
                threading.Thread(target=download_audio, args=(song['url'],ctx.guild.id)).start()
        # Tant qu'il n'y a pas autant de fichier dans audio/ que de musiques dans la queue, on attend
        while len(os.listdir(f'audio/')) < len(queue['queue']):
            await asyncio.sleep(1)
        embed = discord.Embed(title="Playing playlist", description=f"Playing playlist `{name}` (cache finished downloading)", color=0x00ff00)
        await response.edit(embed=embed)
        update_queue(ctx.guild.id, queue)


    @playlist.command(name="list", description="Lists all the playlists")
    async def list_playlist(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        embed = discord.Embed(title="Playlists", description="", color=0x00ff00)
        for name, songs in get_queue(ctx.guild.id)['playlist'].items():
            embed.add_field(name=f"`{name}`", value=f"{len(songs)} songs")
        await ctx.respond(embed=embed)


    @playlist.command(name="show", description="Shows a playlist")
    async def show(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        await ctx.response.defer()
        if name not in get_queue(ctx.guild.id)['playlist'].keys():
            embed = EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
            for name in get_queue(ctx.guild.id)['playlist'].keys():
                embed.add_field(name=f"`{name}`", value="")
            await ctx.respond(embed=embed)
            return
        embed = discord.Embed(title=f"Playlist `{name}`", description="", color=0x00ff00)
        for index, song in enumerate(get_queue(ctx.guild.id)['playlist'][name]):
            embed.add_field(name=f"`{index + 1}.`", value=f"[{song['title']}]({song['url']})")
        await ctx.respond(embed=embed)


    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    new_name: discord.Option(str, "The new name of the playlist", required=True)):
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
        embed = discord.Embed(title="Playlist renamed", description=f"Renamed playlist `{name}` to `{new_name}`",
                            color=0x00ff00)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Playlist(bot))