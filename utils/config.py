import sqlite3
from typing import Optional
import aiosqlite
import asyncio


class DatabaseAccess:
    def __init__(self, copy):
        self._copy = copy
        self._loop = asyncio.get_event_loop()

    async def _song_exists(self, **song_data):
        return await self._get_db('SONG', 'song_id', **song_data) is not None

    async def _asker_exists_wrap(self, asker_id: int):
        return await self._get_db('ASKER', 'asker_id', asker_id=asker_id) is not None

    async def _get_db(self, table: str, *columns: str, all_results: bool = False, joins: list[tuple[str, str]] = None,
                      create_if_none: bool = False, **where):
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            where_str = " " + ' AND '.join([f'{key} = \'{value}\'' for key, value in where.items()])
            if joins is not None:
                joins = " " + ' '.join([f'JOIN {table} ON {condition}' for table, condition in joins])
            else:
                joins = ''
            try:
                await cursor.execute(
                    f'SELECT {", ".join([f"{table}.{column}" for column in columns])} FROM {table}{joins}'
                    f'{" WHERE" if where else ""}{where_str};')
            except sqlite3.OperationalError:
                pass
            results = await cursor.fetchall() if all_results else await cursor.fetchone()
            if results is None and create_if_none:
                await self._create_db(table, **where)
                results = await cursor.fetchone()
            return results

    async def _update_db(self, table: str, columns_values: dict[str, str],
                         **where):
        if self._copy:
            return
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            columns = [f'{key} = ?' for key in columns_values.keys()]
            values = tuple(columns_values.values())
            where = ' AND '.join([f'{key} = \'{value}\'' for key, value in where.items()])
            await cursor.execute(
                f'UPDATE {table} SET {", ".join(columns)} WHERE {where};', values)
            await conn.commit()

    async def _create_db(self, table, **columns_values):
        if self._copy:
            return await self._get_db(table, "*", **columns_values)
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            columns = ', '.join(columns_values.keys())
            values = tuple(columns_values.values())
            await cursor.execute(f'INSERT INTO {table} ({columns}) VALUES ({("?, " * len(columns_values))[:-2]});',
                                 values)
            await conn.commit()
        return await self._get_db(table, "*", **columns_values)

    async def _delete_db(self, table: str, **where):
        if self._copy:
            return
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            where = ' AND '.join([f'{key} = \'{value}\'' for key, value in where.items()])
            await cursor.execute(f'DELETE FROM {table} WHERE {where};')
            await conn.commit()


class Asker(DatabaseAccess):
    def __init__(self, copy=False):
        super().__init__(copy)
        self._id = None
        self._discord_id = None

    @classmethod
    async def from_id(cls, discord_id, is_copy=False) -> 'Asker':
        self = cls(is_copy)
        asker = await self._get_db('ASKER', 'asker_id', discord_id=discord_id)
        if asker is not None:
            self._id = asker[0]
            self._discord_id = discord_id
        else:
            self._discord_id = discord_id
            await self._create_db('ASKER', discord_id=discord_id)
            self._id = (await self._get_db('ASKER', 'asker_id', discord_id=discord_id))[0]
        return self

    @property
    def id(self) -> int:
        return self._id

    @property
    def discord_id(self) -> int:
        return self._discord_id


class Song(DatabaseAccess):
    def __init__(self, copy=False):
        super().__init__(copy)
        self._id = None
        self._name = None
        self._url = None
        self._asker = None

    @classmethod
    async def create(cls, name: str, url: str, asker: Asker, is_copy=False) -> 'Song':
        self = cls(is_copy)
        if await self._song_exists(url=url):
            song = await self._get_db('SONG', 'song_id', 'name', 'url', name=name, url=url)
            self._id, self._name, self._url = song
            self._asker = asker
            return self
        self._name = name
        self._url = url
        self._asker = asker
        self._id = (await self._create_db('SONG', name=name, url=url))[0]
        return self

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self) -> str:
        return self._name

    @property
    def title(self) -> str:
        return self._name

    @property
    def url(self) -> str:
        return self._url

    @property
    def asker(self) -> Optional[Asker]:
        return self._asker

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class Playlist(DatabaseAccess):
    def __init__(self, copy):
        super().__init__(copy)
        self._id: int | None = None
        self._name: str | None = None
        self._songs: list[Song] | None = None

    @classmethod
    async def from_id(cls, playlist_id, is_copy=False) -> 'Playlist':
        self = cls(is_copy)
        self._id = playlist_id
        playlist = await self._get_db('PLAYLIST', 'name', playlist_id=playlist_id)
        if playlist is not None:
            self._name = playlist[0]
        songs = await self._get_db('SONG', 'song_id', 'name', 'url', 'discord_id', all_results=True,
                                   joins=[('PLAYLIST_SONG', 'SONG.song_id = PLAYLIST_SONG.song_id'),
                                          ('ASKER', 'PLAYLIST_SONG.asker = ASKER.asker_id')],
                                   playlist_id=playlist_id)

        self._songs = [Song.create(name, url, asker, song_id) for song_id, name, url, asker in songs]
        return self

    @classmethod
    async def create(cls, name: str, songs: list[Song], guild_id) -> 'Playlist':
        self = cls(False)
        self._name = name
        self._songs = songs
        await self._create_db('PLAYLIST', name=name)
        self._id = (await self._get_db('PLAYLIST', 'playlist_id', name=name))[0]
        for song in songs:
            await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker)
        await self._create_db('SERVER_PLAYLIST', server_id=guild_id, playlist_id=self._id)
        return self

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._loop.create_task(self._update_db('PLAYLIST', {"name": value}, playlist_id=self._id))

    @property
    def songs(self) -> list[Song]:
        return self._songs

    async def add_song(self, song: Song):
        self._songs.append(song)
        await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker)

    async def remove_song(self, song: Song):
        self._songs.remove(song)
        await self._delete_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id)


class UserPlaylistAccess(DatabaseAccess):
    def __init__(self, copy):
        super().__init__(copy)
        self._user_id: int | None = None
        self._playlists: set[Playlist] | None = None

    @classmethod
    async def from_id(cls, user_id, is_copy=False) -> 'UserPlaylistAccess':
        self = cls(is_copy)
        self._user_id = user_id
        playlists = await self._get_db('USER_PLAYLIST', 'playlist_id', all_results=True)
        self._playlists = {Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
        return self

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def playlists(self) -> set[Playlist]:
        return self._playlists

    async def add_playlist(self, playlist: Playlist):
        self._playlists.add(playlist)
        await self._create_db('USER_PLAYLIST', user_id=self._user_id, playlist_id=playlist.id)

    async def remove_playlist(self, playlist: Playlist):
        self._playlists.remove(playlist)
        await self._delete_db('USER_PLAYLIST', user_id=self._user_id, playlist_id=playlist.id)

    async def get_playlist(self, playlist_id):
        for playlist in self._playlists:
            if playlist.id == playlist_id:
                return playlist
        return await Playlist.from_id(playlist_id, is_copy=self._copy)


class Config(DatabaseAccess):
    def __init__(self, copy):
        super().__init__(copy)
        self.guild_id: int | None = None
        self._loop_song: bool | None = None
        self._loop_queue: bool | None = None
        self._random: bool | None = None
        self._volume: int | None = None
        self._position: int | None = None
        self._queue: list[Song] | None = None
        self._playlists: set[Playlist] | None = None

    @classmethod
    async def get_config(cls, guild_id, is_copy=False) -> 'Config':
        self = cls(is_copy)
        self.guild_id = guild_id
        server = await self._get_db('SERVER', '*', server_id=guild_id)
        if server is None and not is_copy:
            await self._create_db('SERVER', server_id=guild_id, loop_song=False, loop_queue=False, random=False,
                                  volume=100,
                                  position=0)
            server = await self._get_db('SERVER', '*', server_id=guild_id)
        if server is not None:
            self._loop_song = server[1]
            self._loop_queue = server[2]
            self._random = server[3]
            self._volume = server[4]
            self._position = server[5]
        songs = await self._get_db('SONG', 'song_id', 'name', 'url', 'discord_id', all_results=True,
                                   joins=[('QUEUE', 'SONG.song_id = QUEUE.song_id'),
                                          ('ASKER', 'QUEUE.asker = ASKER.asker_id')],
                                   server_id=guild_id)
        self._queue = [Song.create(name, url, asker, song_id) for song_id, name, url, asker in songs]
        playlists = await self._get_db('PLAYLIST', 'playlist_id', all_results=True)
        self._playlists = {Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
        return self

    @staticmethod
    async def config_exists(guild_id):
        self = Config(True)
        return await self._get_db('SERVER', 'server_id', server_id=guild_id) is not None

    @classmethod
    async def create_config(cls, guild_id):
        self = cls(False)
        self.guild_id = guild_id
        await self._create_db('SERVER', server_id=guild_id, loop_song=False, loop_queue=False, random=False, volume=100,
                              position=0)
        return self

    @property
    def loop_song(self) -> bool:
        return self._loop_song

    @loop_song.setter
    def loop_song(self, value):
        self._loop_song = value
        self._loop.create_task(self._update_db('SERVER', {"loop_song": value}, server_id=self.guild_id))

    @property
    def loop_queue(self) -> bool:
        return self._loop_queue

    @loop_queue.setter
    def loop_queue(self, value):
        self._loop_queue = value
        self._loop.create_task(self._update_db('SERVER', {"loop_queue": value}, server_id=self.guild_id))

    @property
    def random(self) -> bool:
        return self._random

    @random.setter
    def random(self, value):
        self._random = value
        self._loop.create_task(self._update_db('SERVER', {"random": value}, server_id=self.guild_id))

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._loop.create_task(self._update_db('SERVER', {"volume": value}, server_id=self.guild_id))

    @property
    def position(self) -> int:
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self._loop.create_task(self._update_db('SERVER', {"position": value}, server_id=self.guild_id))

    @property
    def queue(self) -> list[Song]:
        return self._queue

    @property
    def playlists(self) -> set[Playlist]:
        return self._playlists

    async def clear_queue(self):
        self._queue.clear()
        await self._delete_db('QUEUE', server_id=self.guild_id)

    async def add_to_queue(self, song: Song):
        self._queue.append(song)
        await self._create_db('QUEUE', song_id=song.id, server_id=self.guild_id, asker=song.asker.id)

    async def remove_from_queue(self, song: Song):
        self._queue.remove(song)
        await self._delete_db('QUEUE', song_id=song.id, server_id=self.guild_id)

    async def edit_queue(self, new_queue: list[Song]):
        await self.clear_queue()
        for song in new_queue:
            await self.add_to_queue(song)

    async def add_playlist(self, playlist: Playlist):
        self._playlists.add(playlist)
        await self._create_db('PLAYLIST', playlst_id=playlist.id, name=playlist.name)
        for song in playlist.songs:
            await self._create_db('PLAYLIST_SONG', playlist_id=playlist.id, song_id=song.id, asker=song.asker)

    async def remove_playlist(self, playlist: Playlist):
        self._playlists.remove(playlist)
        await self._delete_db('PLAYLIST', playlist_id=playlist.id)
        await self._delete_db('PLAYLIST_SONG', playlist_id=playlist.id)

    async def get_playlist(self, playlist_id):
        for playlist in self._playlists:
            if playlist.id == playlist_id:
                return playlist
        return await Playlist.from_id(playlist_id, is_copy=self._copy)
