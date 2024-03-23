from concurrent.futures import ThreadPoolExecutor
from typing import Union, Optional

from discord.commands import SlashCommandGroup

from utils.config import Playlist, PlaylistType
from utils.utils import *


class Playlists(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    playlist = SlashCommandGroup(name="playlist", description="Commands related to playlists")

    create = playlist.create_subgroup(name="create", description="Creates a playlist")

    @create.command(name="from-queue", description="Creates a playlist from the queue")
    async def create_from_queue(self, ctx: discord.ApplicationContext,
                                name: discord.Option(str, "The name of the playlist", required=True),
                                playlist_type: discord.Option(str, "The type of the playlist", required=False,
                                                              choices=["server", "user"], default="server")):
        await ctx.response.defer()
        if len(name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        config = await Config.get_config(ctx.interaction.guild.id, False) if playlist_type == "server" else \
            await UserPlaylistAccess.from_id(ctx.user.id)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if name in [playlist.name for playlist in config.playlists]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                    color=0xff0000))
        playlist = await Playlist.create(name, config.queue,
                                         ctx.guild.id if playlist_type == "server" else ctx.user.id,
                                         PlaylistType.SERVER if playlist_type == "server" else PlaylistType.USER)
        await config.add_playlist(playlist)
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))

    @create.command(name="from-youtube", description="Creates a playlist from a youtube playlist")
    async def create_from_youtube(self, ctx: discord.ApplicationContext,
                                  url: discord.Option(str, "The url of the playlist", required=True),
                                  name: discord.Option(str, "The name of the playlist", required=False),
                                  playlist_type: discord.Option(str, "The type of the playlist", required=False,
                                                                choices=["server", "user"], default="server")):
        await ctx.response.defer()
        try:
            playlist = pytube.Playlist(url)
            if name is None:
                name = playlist.title
            if len(name) > 20:
                return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
            config = await Config.get_config(ctx.interaction.guild.id, False) if playlist_type == "server" else \
                await UserPlaylistAccess.from_id(ctx.user.id)
            if name in [playlist.name for playlist in config.playlists]:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                        color=0xff0000))
            playlist = await Playlist.create(name,
                                             [await
                                              Song.create(video.title, video.watch_url,
                                                          await Asker.from_id(ctx.user.id)) for video in
                                              playlist.videos],
                                             ctx.guild.id if playlist_type == "server" else ctx.user.id,
                                             PlaylistType.SERVER if playlist_type == "server" else PlaylistType.USER
                                             )
            await config.add_playlist(playlist)
            await ctx.respond(
                embed=discord.Embed(title="Playlist", description=f"Playlist {name} created.", color=0x00ff00))
        except PytubeRegexMatchError:
            await ctx.respond(
                embed=discord.Embed(title="Error", description="You must use an url of a youtube playlist",
                                    color=0xff0000))

    @playlist.command(name="delete", description="Deletes a playlist")
    async def delete(self, ctx: discord.ApplicationContext,
                     name: discord.Option(str, "The name of the playlist", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        await ctx.response.defer()
        config: Union[Config, UserPlaylistAccess]
        if name.endswith(" - SERVER"):
            config = await Config.get_config(ctx.guild.id, False)
            name = name[:-8]
        elif name.endswith(" - USER"):
            config = await UserPlaylistAccess.from_id(ctx.user.id)
            name = name[:-6]
        else:
            user_config = await UserPlaylistAccess.from_id(ctx.user.id)
            server_config = await Config.get_config(ctx.guild.id, False)
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing server playlists:",
                                                value="\n".join(
                                                    [playlist.name for playlist in server_config.playlists]))
                                     .add_field(name="Existing user playlists:",
                                                value="\n".join([playlist.name for playlist in user_config.playlists])))
        if name not in [playlist.name for playlist in config.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in config.playlists])))
        await config.remove_playlist([playlist for playlist in config.playlists if playlist.name == name][0])
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Playlist {name} deleted.", color=0x00ff00))

    @playlist.command(name="add", description="Adds a song to a playlist")
    async def add(self, ctx: discord.ApplicationContext,
                  name: discord.Option(str, "The name of the playlist", required=True,
                                       autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                  query: discord.Option(str, "The YouTube video to add to the playlist", required=True)):
        await ctx.response.defer()
        config, name = await self.get_config(ctx, name)
        if config is None:
            return
        try:
            url = pytube.YouTube(query).watch_url
            try:
                await [playlist for playlist in config.playlists if playlist.name == name][0].add_song(
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
        await ctx.response.defer()
        config, name = await self.get_config(ctx, name)
        if config is None:
            return
        if song not in [songs.name for songs in
                        [playlist for playlist in config.playlists if playlist.name == name][0].songs]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="This song is not in the playlist.", color=0xff0000))
        song = [song for song in [playlist for playlist in config.playlists if playlist.name == name][0].songs if
                song.name == song][0]
        await [playlist for playlist in config.playlists if playlist.name == name][0].remove_song(song)
        await ctx.respond(
            embed=discord.Embed(title="Playlist", description=f"Song {song.name} removed from playlist {name}.",
                                color=0x00ff00))

    @playlist.command(name="play", description="Plays a playlist")
    async def play(self, ctx: discord.ApplicationContext,
                   name: discord.Option(str, "The name of the playlist", required=True,
                                        autocomplete=discord.utils.basic_autocomplete(get_playlists))):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        user_playlist = await UserPlaylistAccess.from_id(ctx.user.id)
        playlist = []
        if name.endswith(" - SERVER") and name[:-8] in [playlist.name for playlist in config.playlists]:
            playlist = [playlist for playlist in config.playlists if playlist.name == name[:-8]]
        elif name.endswith(" - USER") and name[:-6] in [playlist.name for playlist in user_playlist.playlists]:
            playlist = [playlist for playlist in user_playlist.playlists if playlist.name == name[:-6]]
        if not playlist:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing server playlists:",
                                                value="\n".join([playlist.name for playlist in config.playlists]))
                                     .add_field(name="Existing user playlists:",
                                                value="\n".join(
                                                    [playlist.name for playlist in user_playlist.playlists])))

        await config.edit_queue(playlist[0].songs)
        config.position = 0
        pool = ThreadPoolExecutor()
        for song in config.queue:
            video = pytube.YouTube(song.url)
            if video.age_restricted:
                await ctx.respond(embed=discord.Embed(title="Error",
                                                      description=f"The [video]({song.url}) is age restricted",
                                                      color=0xff0000))
                config.queue.remove(song)
                await (await config.get_playlist(playlist[0].id)).remove_song(song)
                continue
            if video.length > 12000:
                await ctx.respond(embed=discord.Embed(title="Error",
                                                      description=f"The video [{video.title}]({song.url}) "
                                                                  f"is too long",
                                                      color=0xff0000))
            else:
                pool.submit(download, song.url, download_logger=logging.getLogger("Audio-Downloader"))
        pool.shutdown(wait=True)
        if ctx.guild.voice_client is None:
            await ctx.user.voice.channel.connect()
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(
                embed=discord.Embed(title="Play", description=f"Playing {config.queue[config.position].name}",
                                    color=0x00ff00))
            await play_song(ctx, config.queue[config.position].url)
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
        await ctx.response.defer()
        config, name = await self.get_config(ctx, name)
        if config is None:
            return
        embed = discord.Embed(title=name, color=0x00ff00)
        for index, song in enumerate([playlist for playlist in config.playlists if playlist.name == name][0].songs):
            embed.add_field(name=f"{index + 1}.", value=f"__[{song.name}]({song.url})__")
            if index == 23 and len([playlist for playlist in config.playlists if playlist.name == name][0].songs) > 24:
                embed.add_field(name="...", value="...")
                break
        await ctx.respond(embed=embed)

    @playlist.command(name="rename", description="Renames a playlist")
    async def rename(self, ctx: discord.ApplicationContext,
                     name: discord.Option(str, "The name of the playlist", required=True,
                                          autocomplete=discord.utils.basic_autocomplete(get_playlists)),
                     new_name: discord.Option(str, "The new name of the playlist", required=True)):
        await ctx.response.defer()
        if len(new_name) > 20:
            return await ctx.respond(embed=EMBED_ERROR_NAME_TOO_LONG)
        config, name = await self.get_config(ctx, name)
        if config is None:
            return
        if name not in [playlist.name for playlist in config.playlists]:
            return await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                                     .add_field(name="Existing playlists:",
                                                value="\n".join([playlist.name for playlist in config.playlists])))
        if new_name in [playlist.name for playlist in config.playlists]:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="A playlist with this name already exists.",
                                    color=0xff0000))
        new_playlist = await Playlist.create(new_name,
                                             [playlist for playlist in config.playlists if playlist.name == name][
                                                 0].songs, ctx.guild.id if isinstance(config, Config) else ctx.user.id,
                                             PlaylistType.SERVER if isinstance(config, Config) else PlaylistType.USER)
        await config.remove_playlist([playlist for playlist in config.playlists if playlist.name == name][0])
        await config.add_playlist(new_playlist)
        await ctx.respond(embed=discord.Embed(title="Playlist", description=f"Playlist {name} renamed to {new_name}.",
                                              color=0x00ff00))

    @staticmethod
    async def get_config(ctx: discord.ApplicationContext, playlist_name: str) -> \
            Optional[tuple[Union[Config, UserPlaylistAccess], str]]:
        if playlist_name.endswith(" - SERVER"):
            config = await Config.get_config(ctx.guild.id, False)
            playlist_name = playlist_name[:-8]
        elif playlist_name.endswith(" - USER"):
            config = await UserPlaylistAccess.from_id(ctx.user.id)
            playlist_name = playlist_name[:-6]
        else:
            config = await Config.get_config(ctx.guild.id, False)
            user_config = await UserPlaylistAccess.from_id(ctx.user.id)
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                              .add_field(name="Existing server playlists:",
                                         value="\n".join([playlist.name for playlist in config.playlists]))
                              .add_field(name="Existing user playlists:",
                                         value="\n".join([playlist.name for playlist in user_config.playlists])))
            return None
        if playlist_name not in [playlist.name for playlist in config.playlists]:
            await ctx.respond(embed=EMBED_ERROR_PLAYLIST_NAME_DOESNT_EXIST
                              .add_field(name="Existing playlists:",
                                         value="\n".join([playlist.name for playlist in config.playlists])))
            return None
        return config, playlist_name


def setup(bot):
    bot.add_cog(Playlists(bot))
