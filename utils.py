import io
from enum import Enum
import logging
import discord
import os
import random
import ffmpeg
import pydub
import pytube
import asyncio
import discord.ext.pages
from discord.ext import commands
import requests
import aiosqlite


def download(url: str, file_format: str = "mp3"):
    """Download a video from a YouTube URL"""
    if not url.startswith("https://youtube.com/watch?v="):
        if os.path.exists(f"cache/{format_name(url.split('/')[-1])}"):
            logging.info(f"{url.split('/')[-1]} already in cache as cache/{format_name(url.split('/')[-1])}")
            return f"cache/{format_name(url.split('/')[-1])}"
        r = requests.get(url)
        with open(f"cache/{format_name(url.split('/')[-1])}", "wb") as f:
            f.write(r.content)
        logging.info(f"Downloaded {url.split('/')[-1]} to cache/{format_name(url.split('/')[-1])}")
        return f"cache/{format_name(url.split('/')[-1])}"
    stream = pytube.YouTube(url)
    video_id = stream.video_id
    if os.path.exists(f"cache/{format_name(stream.title)}.{file_format}"):
        logging.info(
            f"{stream.title} already in cache as cache/{format_name(stream.title)}.{file_format} (video id: {video_id})")
        return f"cache/{format_name(stream.title)}.{file_format}"
    stream = stream.streams.filter(only_audio=True).first()
    stream.download(filename=f"cache/{format_name(stream.title)}.{file_format}")
    logging.info(f"Downloaded {stream.title} to cache/{format_name(stream.title)}.{file_format} (video id: {video_id})")
    return f"cache/{format_name(stream.title)}.{file_format}"


class Sinks(Enum):
    mp3 = discord.sinks.MP3Sink()
    wav = discord.sinks.WaveSink()
    ogg = discord.sinks.OGGSink()
    mp4 = discord.sinks.MP4Sink()


async def finished_record_callback(sink, channel: discord.TextChannel):
    mention_strs = []
    audio_segs: list[pydub.AudioSegment] = []
    files: list[discord.File] = []

    longest = pydub.AudioSegment.empty()
    for user_id in sink.audio_data.keys():
        mention_strs.append(f"<@{user_id}>")
    message = await channel.send(
        f"## Recorded {', '.join(mention_strs)}\nProcessing audio" if len(
            mention_strs) > 1 else f"Recorded {mention_strs[0]}\nProcessing audio" if len(
            mention_strs) == 1 else "Recorded no one")

    for user_id, audio in sink.audio_data.items():
        seg = pydub.AudioSegment.from_file(audio.file, format=sink.encoding)

        # Determine the longest audio segment
        if len(seg) > len(longest):
            audio_segs.append(longest)
            longest = seg
        else:
            audio_segs.append(seg)

        audio.file.seek(0)
        files.append(discord.File(audio.file, filename=f"{channel.guild.get_member(user_id).name}.{sink.encoding}"))

    for seg in audio_segs:
        longest = longest.overlay(seg)
    with io.BytesIO() as f:
        longest.export(f, format=sink.encoding)
        await message.edit(content=f"## Recorded {', '.join(mention_strs)}" if len(
            mention_strs) > 1 else f"Recorded {mention_strs[0]}" if len(
            mention_strs) == 1 else "Recorded no one",
                           files=files + [
                               discord.File(f, filename=f"record.{sink.encoding}")] if sink.encoding != "wav" else files
                           )


async def disconnect_from_channel(state: discord.VoiceState, bot: commands.Bot):
    ok = False
    for client in bot.voice_clients:
        for guild in client.client.guilds:
            if guild.id == state.channel.guild.id:
                await client.disconnect(force=True)
                queue = await get_config(guild.id, False)
                await queue.edit_queue([])
                await queue.set_position(0)
                await queue.close()
                ok = True
            if ok:
                break
        if ok:
            break


class SelectVideo(discord.ui.Select):
    def __init__(self, videos: list[pytube.YouTube], ctx, download_file, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.download = download_file
        options = []
        for video in videos:
            if video in options:
                continue
            options.append(discord.SelectOption(label=video.title, value=video.watch_url))
        self.options = options

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.edit(
            embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}",
                                color=0x00ff00), view=None)
        queue = await get_config(interaction.guild.id, False)
        if self.download:
            stream = pytube.YouTube(self.values[0]).streams.filter(only_audio=True).first()
            if pytube.YouTube(self.values[0]).length > 12000:
                await queue.close()
                return await interaction.message.edit(embed=discord.Embed(title="Error",
                                                                          description=f"The video [{pytube.YouTube(self.values[0]).title}]({self.values[0]}) is too long",
                                                                          color=0xff0000))
            stream.download(filename=f"cache/{format_name(stream.title)}.mp3")
            await queue.close()
            return await interaction.message.edit(
                embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
                file=discord.File(f"cache/{format_name(stream.title)}", filename=f"{format_name(stream.title)}.mp3"),
                view=None)
        if not queue.queue:
            await queue.set_position(0)
            await queue.add_song_to_queue(
                {'title': pytube.YouTube(self.values[0]).title, 'url': self.values[0], 'asker': interaction.user.id})
            await queue.close()
        else:
            await queue.add_song_to_queue(
                {'title': pytube.YouTube(self.values[0]).title, 'url': self.values[0], 'asker': interaction.user.id})
            await queue.close()
        if interaction.guild.voice_client is None:
            await interaction.user.voice.channel.connect()
        if not interaction.guild.voice_client.is_playing():
            await interaction.message.edit(embed=discord.Embed(title="Play",
                                                               description=f"Playing song [{pytube.YouTube(self.values[0]).title}]({self.values[0]})",
                                                               color=0x00ff00))
            await play_song(self.ctx, queue.queue[queue.position]['url'])
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue",
                                                               description=f"Song [{pytube.YouTube(self.values[0]).title}]({self.values[0]}) added to queue.",
                                                               color=0x00ff00))


class Research(discord.ui.View):
    def __init__(self, videos: list[pytube.YouTube], ctx: discord.ApplicationContext, download_file: bool, *items,
                 timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos, ctx, download_file))


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
DATABASE_FILE = "database/database.db"


async def get_playlists(ctx: discord.AutocompleteContext):
    config = await get_config(ctx.interaction.guild.id, True)
    return [playlist.name for playlist in config.playlists]


async def get_playlists_songs(ctx: discord.AutocompleteContext):
    config = await get_config(ctx.interaction.guild.id, True)
    return [song['title'] for song in
            [playlist for playlist in config.playlists if playlist.name == ctx.options['playlist']][0].songs]


async def get_queue_songs(ctx: discord.AutocompleteContext):
    queue = await get_config(ctx.interaction.guild.id, True)
    if len(queue.queue) < 1:
        return []
    queue_ = queue.queue.copy()
    queue_.pop(queue.position)
    return [song['title'] for song in queue_]


def format_name(name: str):
    """Replace |, /, backslash, <, >, :, *, ?, ", and ' with a character with their unicode"""
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


def get_index_from_title(title, list_to_check):
    for index, song in enumerate(list_to_check):
        if song['title'] == title:
            return index
    return -1


async def change_song(ctx: discord.ApplicationContext):
    queue = await get_config(ctx.guild.id, False)
    if not queue.queue:
        await queue.close()
        return
    if queue.position >= len(queue.queue) - 1 and not queue.loop_queue:
        await queue.set_position(0)
        await queue.edit_queue([])
        return await queue.close()
    if queue.position >= len(queue.queue) - 1 and queue.loop_queue:
        await queue.set_position(-1)
    if not queue.loop_song:
        if queue.random and len(queue.queue) > 1:
            await queue.set_position(random.choice(list(set(range(0, len(queue.queue))) - {queue.position})))
        elif len(queue.queue) < 1:
            await queue.set_position(0)
        else:
            await queue.set_position(queue.position + 1)
    await queue.close()
    try:
        await play_song(ctx, queue.queue[queue.position]['url'])
    except Exception as e:
        logging.error(f"Erreur : {e}")


async def play_song(ctx: discord.ApplicationContext, url: str):
    if ctx.guild.voice_client is None:
        return
    if ctx.guild.voice_client.is_playing():
        ctx.guild.voice_client.stop()
    config = await get_config(ctx.guild.id, True)
    try:
        video = pytube.YouTube(url)
        if video.length > 12000:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"The video [{video.title}]({url}) is too long",
                                    color=0xff0000))

        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(download(url), executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
            config.volume / 100)
        try:
            logging.info(f"Playing song {video.title}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
                                        
        except:
            while ctx.guild.voice_client.is_playing():
                await asyncio.sleep(0.1)
            logging.info(f"Playing song {video.title}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
    except:
        player = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(download(url), executable="./bin/ffmpeg.exe" if os.name == "nt" else "ffmpeg"),
            config.volume / 100)
        try:
            logging.info(f"Playing song {url}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)
        except:
            try:
                await ctx.guild.voice_client.disconnect(force=True)
            except:
                pass
            await ctx.author.voice.channel.connect()
            logging.info(f"Playing song {url}")
            ctx.guild.voice_client.play(player, after=lambda e: asyncio.run(on_play_song_finished(ctx, e)),
                                        wait_finish=True)


async def on_play_song_finished(ctx: discord.ApplicationContext, error=None):
    if error is not None and error:
        logging.error("Error:", error)
        await ctx.respond(
            embed=discord.Embed(title="Error", description="An error occured while playing the song.", color=0xff0000))
    logging.info("Song finished")
    await change_song(ctx)


def convert(audio, file_format):
    stream = ffmpeg.input(audio)
    stream = ffmpeg.output(stream, f"{audio.split('/')[1][:-4]}.{file_format}", format=file_format)
    ffmpeg.run(stream)
    return f"{audio.split('/')[1][:-4]}.{file_format}"


def sql_to_song(sql):
    """Convert a song from the database to a dict"""
    return {"id": sql[0], "title": sql[1], "url": sql[2], "asker": sql[3]}


def song_to_sql(song):
    """Convert a song to a tuple to insert it in the database"""
    return song["id"], song["title"], song["url"], song["asker"]


class Playlist:
    def __init__(self, name, songs, server_id, is_copy):
        self.id = None
        self.__cursor = None
        self.__connexion = None
        self.name = name
        self.songs = songs
        self.server_id = server_id
        self.is_copy = is_copy

    @classmethod
    async def create(cls, name, songs, server_id, is_copy=False):
        self = cls(name, songs, server_id, is_copy)
        await self.init()
        return self

    async def init(self):
        self.__connexion = await aiosqlite.connect(DATABASE_FILE)
        self.__cursor = await self.__connexion.cursor()
        for song in self.songs:
            await self.__cursor.execute("SELECT * FROM SONG WHERE title = ? AND url = ? AND asker = ?",
                                        (song["title"], song["url"], song["asker"]))
            if await self.__cursor.fetchone() is None:
                await self.__cursor.execute("SELECT COUNT(*) FROM SONG")
                song["id"] = await self.__cursor.fetchone()
                song["id"] = song["id"][0] + 1
                await self.__cursor.execute("INSERT INTO SONG VALUES (?, ?, ?, ?)", song_to_sql(song))
                logging.info(f"Added song {song['title']} to database")
        await self.__connexion.commit()
        if self.is_copy:
            await self.close()

    async def add_song(self, song):
        self.songs.append(song)
        if self.is_copy:
            return
        await self.__cursor.execute("SELECT * FROM SONG WHERE title = ? AND url = ? AND asker = ?",
                                    (song["title"], song["url"], song["asker"]))
        if await self.__cursor.fetchone() is None:
            # Si elle n'existe pas on l'ajoute, en ajoutant un id
            await self.__cursor.execute("SELECT COUNT(*) FROM SONG")
            song["id"] = await self.__cursor.fetchone()[0] + 1
            await self.__cursor.execute("INSERT INTO SONG VALUES (?, ?, ?, ?)", song_to_sql(song))
            logging.info(f"Added song {song['title']} to database")
        await self.__cursor.execute("INSERT INTO PLAYLIST VALUES (?, ?, ?, ?)",
                                    (self.name, self.id, song["id"], len(self.songs) - 1))
        logging.info(f"Added song {song['title']} to playlist {self.name} from server {self.server_id}")
        await self.__connexion.commit()

    async def remove_song(self, song):
        self.songs.remove(song)
        if self.is_copy:
            return
        await self.__cursor.execute("DELETE FROM PLAYLIST WHERE server_id = ? AND name = ? AND song_id = ?",
                                    (self.id, self.name, song["id"]))
        logging.info(f"Removed song {song['title']} from playlist {self.name} from server {self.server_id}")
        await self.__connexion.commit()

    async def edit_name(self, name):
        self.name = name
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE PLAYLIST SET name = ? WHERE server_id = ? AND name = ?",
                                    (name, self.server_id, self.name))
        logging.info(f"Edited playlist {self.name} to {name} from server {self.server_id}")
        await self.__connexion.commit()

    async def edit_songs(self, songs):
        self.songs = songs
        if self.is_copy:
            return
        await self.__cursor.execute("DELETE FROM PLAYLIST WHERE server_id = ? AND name = ?",
                                    (self.server_id, self.name))
        logging.info(f"Edited playlist {self.name} from server {self.server_id}")
        for index, song in enumerate(songs):
            await self.__cursor.execute("INSERT INTO PLAYLIST VALUES (?, ?, ?, ?)",
                                        (self.name, self.id, song["id"], index))
            logging.info(f"Added song {song['title']} to playlist {self.name}")
        await self.__connexion.commit()

    async def delete(self):
        await self.__cursor.execute("DELETE FROM PLAYLIST WHERE server_id = ? AND name = ?", (self.id, self.name))
        await self.__connexion.commit()
        logging.info(f"Deleted playlist {self.name} from server {self.server_id}")
        await self.close()

    async def close(self):
        await self.__connexion.close()

    def __eq__(self, other):
        return self.name == other.name and self.songs == other.songs and self.server_id == other.server_id


class Config:
    def __init__(self, server_id, is_copy):
        self._playlists = None
        self._queue = None
        self._position = None
        self._volume = None
        self._random = None
        self._loop_queue = None
        self._loop_song = None
        self.__connexion = None
        self.__cursor = None
        self.id = server_id
        self.is_copy = is_copy

    @classmethod
    async def create(cls, server_id, is_copy):
        self = cls(server_id, is_copy)
        await self.init()
        return self

    async def init(self):
        self.__connexion = await aiosqlite.connect(DATABASE_FILE)
        self.__cursor = await self.__connexion.cursor()
        await self.__cursor.execute("SELECT * FROM SERVER WHERE id = ?", (self.id,))
        config = await self.__cursor.fetchone()
        if config is None:
            await self.__cursor.execute("INSERT INTO SERVER VALUES (?, ?, ?, ?, ?, ?)",
                                        (self.id, False, False, False, 100, 0))
            logging.info(f"Added server {self.id} to database")
            await self.__connexion.commit()
            await self.__cursor.execute("SELECT * FROM SERVER WHERE id = ?", (self.id,))
            config = await self.__cursor.fetchone()
        self._loop_song = config[1]
        self._loop_queue = config[2]
        self._random = config[3]
        self._volume = config[4]
        self._position = config[5]
        queue = await self.__cursor.execute(
            "SELECT id, title, url, asker FROM SONG JOIN QUEUE ON SONG.id = QUEUE.song_id WHERE QUEUE.server_id = ? ORDER BY QUEUE.position",
            (self.id,))
        queue = await queue.fetchall()
        if queue is None:
            self._queue = []
        else:
            self._queue = [sql_to_song(song) for song in queue]
        await self.__cursor.execute("SELECT DISTINCT name FROM PLAYLIST WHERE server_id = ?", (self.id,))
        playlists_name = await self.__cursor.fetchall()
        if playlists_name is None:
            playlists_name = []
        playlists_songs = []
        for playlist in playlists_name:
            await self.__cursor.execute(
                "SELECT id, title, url, asker FROM SONG JOIN PLAYLIST ON SONG.id = PLAYLIST.song_id WHERE PLAYLIST.name = ? ORDER BY PLAYLIST.position",
                playlist)
            playlists_songs.append([sql_to_song(song) for song in await self.__cursor.fetchall() if
                                    await self.__cursor.fetchall() is not None])
        self._playlists = [await Playlist.create(playlists_name[i][0], playlists_songs[i], self.id) for i in
                           range(len(playlists_name))] if playlists_name is not None else []
        if self.is_copy:
            await self.close()

    @property
    def loop_song(self):
        return self._loop_song

    async def set_loop_song(self, value):
        self._loop_song = value
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE SERVER SET loop_song = ? WHERE id = ?", (value, self.id))
        logging.info(f"Toggled loop_song to {value} for server {self.id}")
        await self.__connexion.commit()

    @property
    def loop_queue(self):
        return self._loop_queue

    async def set_loop_queue(self, value):
        self._loop_queue = value
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE SERVER SET loop_queue = ? WHERE id = ?", (value, self.id))
        logging.info(f"Toggled loop_queue to {value} for server {self.id}")
        await self.__connexion.commit()

    @property
    def random(self):
        return self._random

    async def set_random(self, value):
        self._random = value
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE SERVER SET random = ? WHERE id = ?", (value, self.id))
        logging.info(f"Toggled random to {value} for server {self.id}")
        await self.__connexion.commit()

    @property
    def volume(self):
        return self._volume

    async def set_volume(self, value):
        self._volume = value
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE SERVER SET volume = ? WHERE id = ?", (value, self.id))
        logging.info(f"Updated volume to {value} for server {self.id}")
        await self.__connexion.commit()

    @property
    def position(self):
        return self._position

    async def set_position(self, value):
        self._position = value
        if self.is_copy:
            return
        await self.__cursor.execute("UPDATE SERVER SET position = ? WHERE id = ?", (value, self.id))
        logging.info(f"Changed position in queue to {value} for server {self.id}")
        await self.__connexion.commit()

    @property
    def queue(self):
        return self._queue

    async def add_song_to_queue(self, song):
        self._queue.append(song)
        if self.is_copy:
            return
        await self.__cursor.execute("SELECT * FROM SONG WHERE title = ? AND url = ? AND asker = ?",
                                    (song["title"], song["url"], song["asker"]))
        if await self.__cursor.fetchone() is None:
            # Si elle n'existe pas on l'ajoute, en ajoutant un id
            await self.__cursor.execute("SELECT COUNT(*) FROM SONG")
            song["id"] = await self.__cursor.fetchone()
            song["id"] = song["id"][0] + 1
            await self.__cursor.execute("INSERT INTO SONG VALUES (?, ?, ?, ?)", song_to_sql(song))
            logging.info(f"Added song {song['title']} to database")
        else:
            await self.__cursor.execute("SELECT id FROM SONG WHERE title = ? AND url = ? AND asker = ?",
                                        (song["title"], song["url"], song["asker"]))
            song["id"] = await self.__cursor.fetchone()
            song["id"] = song["id"][0]
        await self.__cursor.execute("INSERT INTO QUEUE VALUES (?, ?, ?)", (song["id"], self.id, len(self._queue) - 1))
        logging.info(f"Added song {song['title']} to {self.id} queue")
        await self.__connexion.commit()

    async def remove_song_from_queue(self, song):
        try:
            self._queue.remove(song)
            if self.is_copy:
                return
            await self.__cursor.execute("DELETE FROM QUEUE WHERE server_id = ? AND song_id = ?", (song["id"], self.id))
            logging.info(f"Removed song {song['title']} from {self.id} queue")
            await self.__connexion.commit()
            await self.edit_queue(self._queue)
        except ValueError:
            pass

    async def edit_queue(self, queue):
        self._queue = queue
        if self.is_copy:
            return
        await self.__cursor.execute("DELETE FROM QUEUE WHERE server_id = ?", (self.id,))
        for index, song in enumerate(queue):
            await self.__cursor.execute("INSERT INTO QUEUE VALUES (?, ?, ?)", (song["id"], self.id, index))
        logging.info(f"Fully edited queue for server {self.id}")
        await self.__connexion.commit()

    async def close(self):
        await self.__connexion.close()
        for playlist in self._playlists:
            await playlist.close()

    async def copy(self):
        return await Config.create(self.id, True)

    @property
    def playlists(self):
        return self._playlists

    @playlists.setter
    def playlists(self, value):
        self._playlists = value

    async def add_playlist(self, playlist: Playlist):
        self._playlists.append(playlist)
        if self.is_copy:
            return
        for song_index, song in enumerate(playlist.songs):
            await self.__cursor.execute("INSERT INTO PLAYLIST VALUES (?, ?, ?, ?)",
                                        (playlist.name, self.id, song["id"], song_index))
            logging.info(f"Added song {song['title']} to playlist {playlist.name} from server {self.id}")
        await self.__connexion.commit()

    async def remove_playlist(self, playlist: Playlist):
        self._playlists.remove(playlist)
        if self.is_copy:
            return
        await self.__cursor.execute("DELETE FROM PLAYLIST WHERE server_id = ? AND name = ?", (self.id, playlist.name))
        logging.info(f"Deleted playlist {playlist.name} from server {self.id}")
        await self.__connexion.commit()

    async def edit_playlists(self, playlists: list[Playlist]):
        self._playlists = playlists
        if self.is_copy:
            return
        await self.__cursor.execute("DELETE FROM PLAYLIST WHERE server_id = ?", (self.id,))
        for playlist in playlists:
            for song_index, song in enumerate(playlist.songs):
                await self.__cursor.execute("INSERT INTO PLAYLIST VALUES (?, ?, ?, ?)",
                                            (playlist.name, self.id, song["id"], song_index))
        logging.info(f"Edited all playlists from server {self.id}")
        await self.__connexion.commit()


async def get_config(guild_id, is_copy) -> Config:
    connexion = await aiosqlite.connect(DATABASE_FILE)
    cursor = await connexion.cursor()
    await cursor.execute("SELECT * FROM SERVER WHERE id = ?", (guild_id,))
    config = await cursor.fetchone()
    await connexion.close()
    if config is not None:
        return await Config.create(guild_id, is_copy)
    else:
        connexion = await aiosqlite.connect(DATABASE_FILE)
        cursor = await connexion.cursor()
        await cursor.execute("INSERT INTO SERVER VALUES (?, ?, ?, ?, ?, ?)", (guild_id, False, False, False, 100, 0))
        await connexion.commit()
        await connexion.close()
        return await Config.create(guild_id, is_copy)


class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors"""
    format = "[{asctime}] {levelname} : {message} (" + "{pathname}".replace(os.getcwd(), "").replace("\\", "/").replace(
        "/", ".") + ":{lineno}" + ")\033[0m"
    FORMATS = {
        logging.DEBUG: "\033[34m" + format,  # Blue
        logging.INFO: "\033[32m" + format,  # Green
        logging.WARNING: "\033[33m" + format,  # Yellow
        logging.ERROR: "\033[31m" + format,  # Red
        logging.CRITICAL: "\033[41m" + format  # Red
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%d/%m/%Y %H:%M:%S", style="{")
        return formatter.format(record)


def get_lyrics(title):
    """Get the lyrics of a song"""
    return None
