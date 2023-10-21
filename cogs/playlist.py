import asyncio
import threading

import pytube
from discord.commands import SlashCommandGroup
from discord.ext import commands

from utils import *


class Playlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

    create = playlist.create_subgroup(name="create", description="Creates a playlist")

    @create.command(name="from-queue", description="Creates a playlist from the queue")
    async def create_from_queue(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True)):
        if len(name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        queue = get_queue(ctx.interaction.guild.id)
        if not queue['queue']:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if name in queue['playlist'].keys():
            return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
        queue['playlist'][name] = queue['queue']
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))

    @create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
    async def create_from_youtube(self, ctx: discord.ApplicationContext, url: discord.Option(str, "The url of the playlist", required=True), name: discord.Option(str, "The name of the playlist", required=False)):
        try:
            playlist = pytube.Playlist(url)
            if name is None:
                name = playlist.title
            if len(name) > 20:
                return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            queue = get_queue(ctx.interaction.guild.id)
            if name in queue['playlist'].keys():
                return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
            queue['playlist'][name] = []
            for video in playlist.videos:
                queue['playlist'][name].append({'title': video.title, 'url': video.watch_url})
            update_queue(ctx.interaction.guild.id, queue)
            await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))
        except:
            await ctx.respond(embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist", color=0xff0000))


            

    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
        del queue['playlist'][name]
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=0x00ff00))



    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)), query: discord.Option(str, "The YouTube video to add to the playlist", required=True)):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
        try:
            url = pytube.YouTube(query).watch_url
            try:
                queue['playlist'][name].append({'title': pytube.YouTube(query).title, 'url': url})
                update_queue(ctx.interaction.guild.id, queue)
                await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song added to playlist {name}.", color=0x00ff00))
            except:
                return await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
        except:
            return await ctx.respond(embed=discord.Embed(title="Error", description="You must use an url of a youtube video (the research feature is not available for this command yet)", color=0xff0000))

    @playlist.command(name="remove", description="Removes a song from a playlist")
    async def remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    song: discord.Option(str, "The name of the song", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
        if song not in [song['title'] for song in queue['playlist'][name]]:
            return await ctx.respond(embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=0xff0000))
        queue['playlist'][name].pop(get_index_from_title(song, queue['playlist'][name]))
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song {song} removed from playlist {name}.", color=0x00ff00))


    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
        queue['queue'] = queue['playlist'][name]
        queue['index'] = 0
        update_queue(ctx.interaction.guild.id, queue)
        for song in queue['queue']:
            # On limite le nombre de threads à 5
            while threading.active_count() > 5:
                await asyncio.sleep(0.1)
            if pytube.YouTube(song['url']).length > 12000:
                await ctx.respond(embed=discord.Embed(title="Error", description=f"The video [{pytube.YouTube(song['url']).title}]({song['url']}) is too long", color=0xff0000))
            else:
                threading.Thread(target=download, args=(song['url'],), name=f"Download-{pytube.YouTube(song['url']).video_id}").start()
        if ctx.interaction.guild.voice_client is None:
            await ctx.interaction.user.voice.channel.connect()
        if not ctx.interaction.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Play", description=f"Playing {queue['queue'][queue['index']]['title']}", color=0x00ff00))
            await play_song(ctx, queue['queue'][queue['index']]['url'])
        else:
            await ctx.respond(embed=discord.Embed(title="Queue", description=f"Playlist {name} added to queue.", color=0x00ff00))


    @playlist.command(name="list", description="Lists all the playlists")
    async def list_playlist(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['playlist'] == {}:
            return await ctx.respond(embed=discord.Embed(title="Playlists", description="No playlists.", color=0x00ff00))   
        embed = discord.Embed(title="Playlists", color=0x00ff00)
        for name in queue['playlist'].keys():
            embed.add_field(name=f"__{name}__ :", value=f"{len(queue['playlist'][name])} song{'s' if len(queue['playlist'][name]) > 1 else ''}")
        await ctx.respond(embed=embed)




    @playlist.command(name="show", description="Shows a playlist")
    async def show(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(get_queue(ctx.interaction.guild.id)['playlist'].keys())))
        embed = discord.Embed(title=name, color=0x00ff00)
        for index, song in enumerate(queue['playlist'][name]):
            embed.add_field(name=f"{index}.", value=song['title'])
        await ctx.respond(embed=embed)



    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    new_name: discord.Option(str, "The new name of the playlist", required=True)):
        if len(new_name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        queue = get_queue(ctx.interaction.guild.id)
        if name not in queue['playlist'].keys():
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join(queue['playlist'].keys())))
        if new_name in queue['playlist'].keys():
            return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
        queue['playlist'][new_name] = queue['playlist'][name]
        del queue['playlist'][name]
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.", color=0x00ff00))


def setup(bot):
    bot.add_cog(Playlist(bot))