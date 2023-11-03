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
        queue = await get_config(ctx.interaction.guild.id, False)
        if not queue.queue:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if name in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
        playlist = await Playlist.create(name, queue.queue)
        await queue.add_playlist(playlist)
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))

    @create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
    async def create_from_youtube(self, ctx: discord.ApplicationContext, url: discord.Option(str, "The url of the playlist", required=True), name: discord.Option(str, "The name of the playlist", required=False)):
        try:
            playlist = pytube.Playlist(url)
            if name is None:
                name = playlist.title
            if len(name) > 20:
                return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            queue = await get_config(ctx.interaction.guild.id, False)
            if name in [playlist.name for playlist in queue.playlists]:
                await queue.close()
                return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
            playlist = await Playlist.create(name, [{'title': video.title, 'url': video.watch_url, 'asker': ctx.user.id} for video in playlist.videos])
            await queue.add_playlist(playlist)
            await queue.close()
            await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))
        except:
            await ctx.respond(embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist", color=0xff0000))


            

    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = await get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        await queue.remove_playlist([playlist for playlist in queue.playlists if playlist.name == name][0])
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=0x00ff00))



    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)), query: discord.Option(str, "The YouTube video to add to the playlist", required=True)):
        queue = await get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        try:
            url = pytube.YouTube(query).watch_url
            try:
                await [playlist for playlist in queue.playlists if playlist.name == name][0].add_song({'title': pytube.YouTube(query).title, 'url': url, 'asker': ctx.user.id})
                await queue.close()
                await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song added to playlist {name}.", color=0x00ff00))
            except:
                await queue.close()
                return await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
        except:
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Error", description="You must use an url of a youtube video (the research feature is not available for this command yet)", color=0xff0000))

    @playlist.command(name="remove", description="Removes a song from a playlist")
    async def remove(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    song: discord.Option(str, "The name of the song", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))):
        queue = await get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        if song not in [song['title'] for song in [playlist for playlist in queue.playlists if playlist.name == name][0].songs]:
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=0xff0000))
        await [playlist for playlist in queue.playlists if playlist.name == name][0].remove_song(song)
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song {song} removed from playlist {name}.", color=0x00ff00))


    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = await get_config(ctx.guild.id, False)
        await ctx.response.defer()
        if name not in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        await queue.edit_queue([playlist for playlist in queue.playlists if playlist.name == name][0].songs)
        await queue.set_position(0)
        await queue.close()
        for song in queue.queue:
            # On limite le nombre de threads à 3
            while len([thread for thread in threading.enumerate() if thread.name.startswith("Download-")]) >= 3:
                await asyncio.sleep(0.1)
            if pytube.YouTube(song['url']).length > 12000:
                await ctx.respond(embed=discord.Embed(title="Error", description=f"The video [{pytube.YouTube(song['url']).title}]({song['url']}) is too long", color=0xff0000))
            else:
                threading.Thread(target=download, args=(song['url'],), name=f"Download-{pytube.YouTube(song['url']).video_id}").start()
        if ctx.guild.voice_client is None:
            await ctx.user.voice.channel.connect()
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Play", description=f"Playing {queue.queue[queue.position]['title']}", color=0x00ff00))
            await play_song(ctx, queue.queue[queue.position]['url'])
        else:
            await ctx.respond(embed=discord.Embed(title="Queue", description=f"Playlist {name} added to queue.", color=0x00ff00))


    @playlist.command(name="list", description="Lists all the playlists")
    async def list_playlist(self, ctx: discord.ApplicationContext):
        queue = await get_config(ctx.guild.id, True)
        if not queue.playlists:
            return await ctx.respond(embed=discord.Embed(title="Playlists", description="No playlists.", color=0x00ff00))   
        embed = discord.Embed(title="Playlists", color=0x00ff00)
        for name in [playlist.name for playlist in queue.playlists]:
            embed.add_field(name=f"__{name}__ :", value=f"{len([playlist for playlist in queue.playlists][0].songs)} song{'s' if len([playlist for playlist in queue.playlists][0].songs) > 1 else ''}")
        await ctx.respond(embed=embed)




    @playlist.command(name="show", description="Shows a playlist")
    async def show(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        queue = await get_config(ctx.guild.id, True)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        embed = discord.Embed(title=name, color=0x00ff00)
        for index, song in enumerate([playlist for playlist in queue.playlists if playlist.name == name][0].songs):
            embed.add_field(name=f"{index+1}.", value=f"__[{song['title']}]({song['url']})__")
            if index == 23 and len([playlist for playlist in queue.playlists if playlist.name == name][0].songs) > 24:
                embed.add_field(name="...", value="...")
                break
        await ctx.respond(embed=embed)



    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext, name: discord.Option(str, "The name of the playlist", required=True, autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                    new_name: discord.Option(str, "The new name of the playlist", required=True)):
        if len(new_name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        queue = await get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                .add_field(name="Existing playlists:", value="\n".join([playlist.name for playlist in queue.playlists])))
        if new_name in [playlist.name for playlist in queue.playlists]:
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Error", description="A playlist with this name already exists.", color=0xff0000))
        new_playlist = await Playlist.create(new_name, [playlist for playlist in queue.playlists if playlist.name == name][0].songs)
        await queue.remove_playlist([playlist for playlist in queue.playlists if playlist.name == name][0])
        await queue.add_playlist(new_playlist)
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.", color=0x00ff00))


def setup(bot):
    bot.add_cog(Playlist(bot))