import aiosqlite
import asyncio
import functools


class DatabaseAccess:
    def __init__(self, copy):
        self._copy = copy
        self._loop = asyncio.get_event_loop()

    async def _song_exists(self, **song_data):
        return await self._get_db('SONG', 'id', **song_data) is not None

    @staticmethod
    def _check_copy(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if self._copy:
                raise AttributeError('Cannot modify a copy of the database')
            return await func(self, *args, **kwargs)

        return wrapper

    async def _asker_exists_wrap(self, asker_id: int):
        return await self._get_db('ASKER', 'id', id=asker_id) is not None

    async def _get_db(self, table: str, *columns: str, all_results: bool = False, joins: list[tuple[str, str]] = None,
                      create_if_none: bool = False, **where):
        async with aiosqlite.connect("../database/database.db") as conn:
            cursor = await conn.cursor()
            columns = ', '.join(columns)
            where = ' AND '.join([f'{key} = {value}' for key, value in where.items()])
            if joins is not None:
                joins = ' '.join([f'JOIN {table} ON {condition}' for table, condition in joins])
            await cursor.execute(f'SELECT {columns} FROM {table} {joins} WHERE {where}')
            results = await cursor.fetchall() if all_results else await cursor.fetchone()
            if results is None and create_if_none:
                await self._create_db(table, **where)
                results = await cursor.fetchone()
            return results

    @_check_copy
    async def _update_db(self, table: str, columns_values: dict[str, str],
                         **where):
        async with aiosqlite.connect("../database/database.db") as conn:
            cursor = await conn.cursor()
            columns = ', '.join([f'{key} = ?' for key in columns_values.keys()])
            values = tuple(columns_values.values())
            where = ' AND '.join([f'{key} = {value}' for key, value in where.items()])
            await cursor.execute(f'UPDATE {table} SET {columns} WHERE {where}', values)
            await conn.commit()

    @_check_copy
    async def _create_db(self, table, **columns_values):
        async with aiosqlite.connect("../database/database.db") as conn:
            cursor = await conn.cursor()
            columns = ', '.join(columns_values.keys())
            values = ', '.join(columns_values.values())
            await cursor.execute(f'INSERT INTO {table} ({columns}) VALUES ({"?, " * len(columns_values)})', values)
            await conn.commit()

    @_check_copy
    async def _delete_db(self, table: str, **where):
        async with aiosqlite.connect("../database/database.db") as conn:
            cursor = await conn.cursor()
            where = ' AND '.join([f'{key} = {value}' for key, value in where.items()])
            await cursor.execute(f'DELETE FROM {table} WHERE {where}')
            await conn.commit()


class Asker(DatabaseAccess):
    def __init__(self, copy=False):
        super().__init__(copy)
        self._id = None
        self._discord_id = None

    @classmethod
    async def from_id(cls, discord_id, is_copy=False) -> 'Asker':
        self = cls(is_copy)
        asker = await self._get_db('ASKER', 'id', id=discord_id)
        if asker is not None:
            self._id = asker[0]
            self._discord_id = discord_id
        else:
            self._id = await self._get_db('COUNT(*)', 'ASKER') + 1
            self._discord_id = discord_id
            await self._create_db('ASKER', id=self._id, discord_id=discord_id)
        return self

    @property
    def id(self):
        return self._id

    @property
    def discord_id(self):
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
        if self._song_exists(name=name, url=url):
            song = await self._get_db('SONG', 'id', 'name', 'url', name=name, url=url)
            self._id, self._name, self._url = song
            self._asker = asker
            return self
        self._id = await self._get_db('COUNT(*)', 'SONG') + 1
        self._name = name
        self._url = url
        self._asker = asker
        await self._create_db('SONG', id=self._id, name=name, url=url)
        return self

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._url

    @property
    def asker(self):
        return self._asker

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
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
        playlist = await self._get_db('PLAYLIST', 'name', id=playlist_id)
        if playlist is not None:
            self._name = playlist[0]
        songs = await self._get_db('SONG', 'id', 'name', 'url', 'discord_id', all_results=True,
                                   joins=[('PLAYLIST_SONG', 'SONG.id = PLAYLIST_SONG.song_id'),
                                          ('ASKER', 'PLAYLIST_SONG.asker = ASKER.id')],
                                   playlist_id=playlist_id)

        self._songs = [Song.create(name, url, asker, song_id) for song_id, name, url, asker in songs]
        return self

    @classmethod
    async def create(cls, name: str, songs: list[Song], guild_id) -> 'Playlist':
        self = cls(False)
        self._id = await self._get_db('COUNT(*)', 'PLAYLIST') + 1
        self._name = name
        self._songs = songs
        await self._create_db('PLAYLIST', id=self._id, name=name)
        for song in songs:
            if not await self._song_exists(song.id):
                await self._create_db('SONG', id=song.id, name=song.name, url=song.url)
            await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker)
        await self._create_db('SERVER_PLAYLIST', server_id=guild_id, playlist_id=self._id)
        return self

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._loop.create_task(self._update_db('PLAYLIST', name=value, id=self._id))

    @property
    def songs(self):
        return self._songs

    async def add_song(self, song: Song):
        self._songs.append(song)
        if not await self._song_exists(song.id):
            await self._create_db('SONG', id=song.id, name=song.name, url=song.url)
        await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker)

    async def remove_song(self, song: Song):
        self._songs.remove(song)
        await self._delete_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id)


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
        server = await self._get_db('SERVER', '*', id=guild_id)
        if server is None and not is_copy:
            await self._create_db('SERVER', id=guild_id, loop_song=False, loop_queue=False, random=False, volume=100,
                                  position=0)
            server = await self._get_db('SERVER', '*', id=guild_id)
        if server is not None:
            self._loop_song = server[1]
            self._loop_queue = server[2]
            self._random = server[3]
            self._volume = server[4]
            self._position = server[5]
        songs = await self._get_db('SONG', 'id', 'name', 'url', 'discord_id', all_results=True,
                                   joins=[('QUEUE', 'SONG.id = QUEUE.song_id'),
                                          ('ASKER', 'QUEUE.asker = ASKER.id')],
                                   server_id=guild_id)
        self._queue = [Song.create(name, url, asker, song_id) for song_id, name, url, asker in songs]
        playlists = await self._get_db('PLAYLIST', 'id', all_results=True)
        self._playlists = {Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
        return self

    @property
    def loop_song(self):
        return self._loop_song

    @loop_song.setter
    def loop_song(self, value):
        self._loop_song = value
        self._loop.create_task(self._update_db('SERVER', loop_song=value, id=self.guild_id))

    @property
    def loop_queue(self):
        return self._loop_queue

    @loop_queue.setter
    def loop_queue(self, value):
        self._loop_queue = value
        self._loop.create_task(self._update_db('SERVER', loop_queue=value, id=self.guild_id))

    @property
    def random(self):
        return self._random

    @random.setter
    def random(self, value):
        self._random = value
        self._loop.create_task(self._update_db('SERVER', random=value, id=self.guild_id))

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._loop.create_task(self._update_db('SERVER', volume=value, id=self.guild_id))

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self._loop.create_task(self._update_db('SERVER', position=value, id=self.guild_id))

    @property
    def queue(self):
        return self._queue

    @property
    def playlists(self):
        return self._playlists

    async def clear_queue(self):
        self._queue.clear()
        await self._delete_db('QUEUE', server_id=self.guild_id)

    async def add_to_queue(self, song: Song):
        self._queue.append(song)
        if song.id is None:
            song.id = await self._get_db('COUNT(*)', 'SONG') + 1
        elif song.id not in await self._get_db('SONG', 'id', all_results=True):
            await self._create_db('SONG', id=song.id, name=song.name, url=song.url)
        await self._create_db('QUEUE', song_id=song.id, server_id=self.guild_id, asker=song.asker)

    async def remove_from_queue(self, song: Song):
        self._queue.remove(song)
        await self._delete_db('QUEUE', song_id=song.id, server_id=self.guild_id)

    async def edit_queue(self, new_queue: list[Song]):
        await self.clear_queue()
        for song in new_queue:
            await self.add_to_queue(song)

    async def add_playlist(self, playlist: Playlist):
        self._playlists.add(playlist)
        await self._create_db('PLAYLIST', id=playlist.id, name=playlist.name)
        for song in playlist.songs:
            if not await self._song_exists(song.id):
                await self._create_db('SONG', id=song.id, name=song.name, url=song.url)
            await self._create_db('PLAYLIST_SONG', playlist_id=playlist.id, song_id=song.id, asker=song.asker)

    async def remove_playlist(self, playlist: Playlist):
        self._playlists.remove(playlist)
        await self._delete_db('PLAYLIST', id=playlist.id)
        await self._delete_db('PLAYLIST_SONG', playlist_id=playlist.id)

    async def get_playlist(self, playlist_id):
        for playlist in self._playlists:
            if playlist.id == playlist_id:
                return playlist
        return await Playlist.from_id(playlist_id, is_copy=self._copy)
