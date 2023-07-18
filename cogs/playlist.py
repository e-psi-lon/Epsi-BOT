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

    create = playlist.create_subgroup(name="create", description="Creates a playlist")

    @create.command(name="from-queue", description="Creates a playlist from the queue")
    async def create_from_queue(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True)):
        if len(name) > 20:
            await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            return
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        if name in queue['playlist'].keys():
            await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
            return
        queue['playlist'][name] = queue['queue']
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Success", description=f"Playlist {name} created.", color=0x00ff00))

    @create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
    async def create_from_youtube(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True), query: discord.Option(str, "The url of the playlist", required=True)):
        pass

    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
            return
        del queue['playlist'][name]
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Success", description=f"Playlist {name} deleted.", color=0x00ff00))



    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                query: discord.Option(str, "The url of the song", required=True)):
        pass

    @playlist.command(name="remove", description="Removes a song from a playlist")
    async def remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    song: discord.Option(str, "The name of the song", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
            return
        if song not in [song['title'] for song in queue['playlist'][name]]:
            await ctx.respond(embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=0xff0000))
            return
        queue['playlist'][name].pop(get_index_from_title(song, queue['playlist'][name]))
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Success", description=f"Song {song} removed from playlist {name}.", color=0x00ff00))


    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        pass


    @playlist.command(name="list", description="Lists all the playlists")
    async def list_playlist(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['playlist'] == {}:
            await ctx.respond(embed=discord.Embed(title="Playlists", description="No playlists.", color=0x00ff00))
            return
        embed = discord.Embed(title="Playlists", color=0x00ff00)
        for name in queue['playlist'].keys():
            embed.add_field(name=name, value=f"{len(queue['playlist'][name])} songs")
        await ctx.respond(embed=embed)




    @playlist.command(name="show", description="Shows a playlist")
    async def show(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(get_queue(ctx.interaction.guild.id)['playlist'].keys())))
            return
        embed = discord.Embed(title=name, color=0x00ff00)
        for index, song in enumerate(queue['playlist'][name]):
            embed.add_field(name=index, value=song['title'])
        await ctx.respond(embed=embed)



    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    new_name: discord.Option(str, "The new name of the playlist", required=True)):
        if len(new_name) > 20:
            await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            return
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
            return
        if new_name in queue['playlist'].keys():
            await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
            return
        queue['playlist'][new_name] = queue['playlist'][name]
        del queue['playlist'][name]
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Success", description=f"Playlist {name} renamed to {new_name}.", color=0x00ff00))


def setup(bot):
    bot.add_cog(Playlist(bot))