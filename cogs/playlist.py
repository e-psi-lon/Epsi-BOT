import multiprocessing
from discord.commands import SlashCommandGroup
from pytube.exceptions import RegexMatchError as PytubeRegexMatchError

from utils.config import Playlist
from utils.utils import *


class Playlists(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

    create = playlist.create_subgroup(name="create", description="Creates a playlist")

    @create.command(name="from-queue", description="Creates a playlist from the queue")
    async def create_from_queue(self, ctx: discord.ApplicationContext,
                                name: discord.Option(str, "The name of the playlist", required=True)):
        # TODO: Add an option to create a user playlist instead of a server playlist
        await ctx.response.defer()
        if len(name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        queue = await Config.get_config(ctx.interaction.guild.id, False)
        if not queue.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if name in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                    color=0xff0000))
        playlist = await Playlist.create(name, queue.queue, ctx.guild.id)
        await queue.add_playlist(playlist)
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))

    @create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
    async def create_from_youtube(self, ctx: discord.ApplicationContext,
                                  url: discord.Option(str, "The url of the playlist", required=True),
                                  name: discord.Option(str, "The name of the playlist", required=False)):
        # TODO: Add an option to create a user playlist instead of a server playlist
        await ctx.response.defer()
        try:
            playlist = pytube.Playlist(url)
            if name is None:
                name = playlist.title
            if len(name) > 20:
                return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            queue = await Config.get_config(ctx.interaction.guild.id, False)
            if name in [playlist.name for playlist in queue.playlists]:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                        color=0xff0000))
            playlist = await Playlist.create(name,
                                             [await Song.create(video.title, video.watch_url,
                                                                await Asker.from_id(ctx.user.id)) for
                                              video in playlist.videos], ctx.guild.id)
            await queue.add_playlist(playlist)
            await ctx.respond(
                embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))
        except:
            await ctx.respond(
                embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist",
                                    color=0xff0000))

    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext,
                     name: discord.Option(str, "The name of the playlist", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        # TODO: Add an option to choose between a server playlist and a user playlist to delete
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists])))
        await queue.remove_playlist([playlist for playlist in queue.playlists if playlist.name == name][0])
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=0x00ff00))

    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext,
                  name: discord.Option(str, "The name of the playlist", required=True,
                                       autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                  query: discord.Option(str, "The YouTube video to add to the playlist", required=True)):
        # TODO: handle the case where the user wants to add a song to a user playlist
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists])))
        try:
            url = pytube.YouTube(query).watch_url
            try:
                await [playlist for playlist in queue.playlists if playlist.name == name][0].add_song(
                    await Song.create(pytube.YouTube(query).title, url, await Asker.from_id(ctx.user.id)))
                await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Song added to playlist {name}.",
                                                      color=0x00ff00))
            except IndexError:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
        except PytubeRegexMatchError:
            return await ctx.respond(embed=discord.Embed(title="Error",
                                                         description="You must use an url of a youtube video "
                                                                     "(the research feature is not available for "
                                                                     "this command yet)",
                                                         color=0xff0000))

    @playlist.command(name="remove", description="Removes a song from a playlist")
    async def remove(self, ctx: discord.ApplicationContext,
                     name: discord.Option(str, "The name of the playlist", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                     song: discord.Option(str, "The name of the song", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists_songs))):
        # TODO: handle the case where the user wants to remove a song from a user playlist
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists])))
        if song not in [song.name for song in
                        [playlist for playlist in queue.playlists if playlist.name == name][0].songs]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=0xff0000))
        song = [song for song in [playlist for playlist in queue.playlists if playlist.name == name][0].songs if
                song.name == song][0]
        await [playlist for playlist in queue.playlists if playlist.name == name][0].remove_song(song)
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Song {song.name} removed from playlist {name}.",
                                color=0x00ff00))

    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext,
                   name: discord.Option(str, "The name of the playlist", required=True,
                                        autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, False)
        user_playlist = await UserPlaylistAccess.from_id(ctx.user.id)
        playlist = []
        if name.endswith(" - SERVER") and name[:-8] in [playlist.name for playlist in queue.playlists]:
            playlist = [playlist for playlist in queue.playlists if playlist.name == name[:-8]]
        elif name.endswith(" - USER") and name[:-6] in [playlist.name for playlist in user_playlist.playlists]:
            playlist = [playlist for playlist in user_playlist.playlists if playlist.name == name[:-6]]
        if not playlist:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing server playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists]))
                                     .add_field(name="Existing user playlists:",
                                                value="\n".join(
                                                    [playlist.name for playlist in user_playlist.playlists])))

        await queue.edit_queue(playlist[0].songs)
        queue.position = 0
        q = multiprocessing.Queue()
        p = multiprocessing.Process(target=worker, args=(q,), name="Playlist-Downloader")
        p.start()
        for song in queue.queue:
            video = pytube.YouTube(song.url)
            if video.age_restricted:
                await ctx.respond(embed=discord.Embed(title="Error",
                                                      description=f"The [video]({song.url}) is age restricted",
                                                      color=0xff0000))
                continue
            if video.length > 12000:
                await ctx.respond(embed=discord.Embed(title="Error",
                                                      description=f"The video [{video.title}]({song.url}) "
                                                                  f"is too long",
                                                      color=0xff0000))
            else:
                q.put(song.url)
        q.put(None)
        p.join()
        if ctx.guild.voice_client is None:
            await ctx.user.voice.channel.connect()
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(
                embed=discord.Embed(title="Play", description=f"Playing {queue.queue[queue.position].name}",
                                    color=0x00ff00))
            await play_song(ctx, queue.queue[queue.position].url)
        else:
            await ctx.respond(
                embed=discord.Embed(title="Queue", description=f"Playlist {name} added to queue.", color=0x00ff00))

    @playlist.command(name="list", description="Lists all the playlists")
    async def list_playlist(self, ctx: discord.ApplicationContext,
                            playlist_type: discord.Option(str, "The type of the playlist", required=False,
                                                          choices=["server", "user"])):
        await ctx.response.defer()
        playlists = (await Config.get_config(ctx.guild.id, True) if playlist_type == "server" else
                     await UserPlaylistAccess.from_id(ctx.user.id)).playlists
        if not playlists:
            return await ctx.respond(
                embed=discord.Embed(title="Playlists", description="No playlists.", color=0x00ff00))
        embed = discord.Embed(title="Playlists", color=0x00ff00)
        for name in [playlist.name for playlist in playlists][:25]:
            embed.add_field(name=f"__{name}__ :",
                            value=f"{len([playlist for playlist in playlists][0].songs)} song"
                                  f"{'s' if len([playlist for playlist in playlists][0].songs) > 1 else ''}")
        await ctx.respond(embed=embed)

    @playlist.command(name="show", description="Shows a playlist")
    async def show(self, ctx: discord.ApplicationContext,
                   name: discord.Option(str, "The name of the playlist", required=True,
                                        autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        # TODO: handle the case where the user wants to show a user playlist
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, True)
        user_playlist = await UserPlaylistAccess.from_id(ctx.user.id)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing server playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists]))
                                     .add_field(name="Existing user playlists:",
                                                value="\n".join(
                                                    [playlist.name for playlist in user_playlist.playlists])))
        embed = discord.Embed(title=name, color=0x00ff00)
        for index, song in enumerate([playlist for playlist in queue.playlists if playlist.name == name][0].songs):
            embed.add_field(name=f"{index + 1}.", value=f"__[{song.name}]({song.url})__")
            if index == 23 and len([playlist for playlist in queue.playlists if playlist.name == name][0].songs) > 24:
                embed.add_field(name="...", value="...")
                break
        await ctx.respond(embed=embed)

    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext,
                     name: discord.Option(str, "The name of the playlist", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                     new_name: discord.Option(str, "The new name of the playlist", required=True)):
        # TODO: handle the case where the user wants to rename a user playlist
        await ctx.response.defer()
        if len(new_name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        queue = await Config.get_config(ctx.guild.id, False)
        if name not in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in queue.playlists])))
        if new_name in [playlist.name for playlist in queue.playlists]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                    color=0xff0000))
        new_playlist = await Playlist.create(new_name,
                                             [playlist for playlist in queue.playlists if playlist.name == name][
                                                 0].songs, ctx.guild.id)
        await queue.remove_playlist([playlist for playlist in queue.playlists if playlist.name == name][0])
        await queue.add_playlist(new_playlist)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.",
                                              color=0x00ff00))


def worker(queue: multiprocessing.Queue):
    worker_logger = logging.getLogger("Playlist-Downloader")
    while True:
        song_url = queue.get()
        if song_url is None:
            break
        download(song_url, download_logger=worker_logger)
    queue.close()
    worker_logger.info("Playlist-Downloader process ended")


def setup(bot):
    bot.add_cog(Playlists(bot))
