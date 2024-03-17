from typing import Optional, Union
import aiosqlite
import asyncio
from pypika import Table, Query, Field
import logging


logger = logging.getLogger("__main__")

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

def unformat_name(name: str):
    """Replace unicode characters with |, /, backslash, <, >, :, *, ?, ", and '"""
    return name.replace("u01C0", "|") \
        .replace("u2215", "/") \
        .replace("u2216", "\\") \
        .replace("u003C", "<") \
        .replace("u003E", ">") \
        .replace("u02D0", ":") \
        .replace("u2217", "*") \
        .replace("u003F", "?") \
        .replace("u0022", '"') \
        .replace("u0027", "'")

class JoinCondition:
    def __init__(self, first_table: str, second_table: str, first_column: str, second_column: str):
        self.first_table = first_table
        self.second_table = second_table
        self.first_column = first_column
        self.second_column = second_column


class DatabaseAccess:
    def __init__(self, copy):
        self._copy = copy
        self._loop = asyncio.get_event_loop()

    async def _song_exists(self, **song_data) -> bool:
        return await self._get_db('SONG', 'song_id', **song_data) is not None

    async def _asker_exists(self, asker_id: int) -> bool:
        return await self._get_db('ASKER', 'asker_id', asker_id=asker_id) is not None

    async def _get_db(self, table: str, *columns: str, all_results: bool = False, joins: Optional[list[JoinCondition]] = None,
                    create_if_none: bool = False, order_by: Optional[str] = None, **where) -> Optional[Union[list[tuple], tuple]]:
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table = Table(table)
            query = Query.from_(table)
            for key, value in where.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.where(getattr(Table(table_name), column) == value)
                else:
                    query = query.where(getattr(table, key) == value)
            if joins is not None:
                for join in joins:
                    table1 = Table(join.first_table)
                    table2 = Table(join.second_table)
                    query = query.join(table2).on(getattr(table1, join.first_column) == getattr(table2, join.second_column))
            if order_by is not None:
                query = query.orderby(order_by)
            if columns[0] != '*':
                for column in columns:
                    column = column.split('.')
                    if len(column) > 1:
                        if column[1] != '*':
                            query = query.select(getattr(Table(column[0]), column[1]))
                        else:
                            query = query.select(Field('*', table=column[0]))
                    else:
                        query = query.select(getattr(table, column[0]))
            else:
                query = query.select("*")
            query = str(query)
            logger.info(f"Executing query: {query}")
            await cursor.execute(query)
            results = await cursor.fetchall() if all_results else await cursor.fetchone()
            if results is None and create_if_none:
                await self._create_db(table, **where)
                results = await cursor.fetchone()
            return results

    async def _update_db(self, table: str, columns_values: dict[str, str],
                         **where) -> None:
        if self._copy:
            return
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table = Table(table)
            query = Query.update(table).set(columns_values)
            for key, value in where.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.where(getattr(Table(table_name), column) == value)
            query = str(query)
            logger.info(f"Executing query: {query}")
            await cursor.execute(query)
            await conn.commit()

    async def _create_db(self, table, **columns_values) -> Optional[Union[list[tuple], tuple]]:
        if self._copy:
            return await self._get_db(table, f"{table}.*", **columns_values)
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table_ = Table(table)
            query = Query.into(table_).columns(*columns_values.keys()).insert(*columns_values.values())
            query = str(query)
            logger.info(f"Executing query: {query}")
            await cursor.execute(query)
            await conn.commit()
        return await self._get_db(table, f"*", **columns_values)

    async def _delete_db(self, table: str, **where) -> None:
        if self._copy:
            return
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table = Table(table)
            query = Query.from_(table).delete()
            for key, value in where.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.where(getattr(Table(table_name), column) == value)
                else:
                    query = query.where(getattr(table, key) == value)
            query = str(query)
            logger.info(f"Executing query: {query}")
            await cursor.execute(query)
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
    
    def __str__(self) -> str:
        return f"Asker: {self.discord_id}"


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
            song = await self._get_db('SONG', 'song_id', 'name', 'url', name=format_name(name), url=url)
            self._id, self._name, self._url = song
            self._name = unformat_name(self._name)
            self._asker = asker
            return self
        self._name = name
        self._url = url
        self._asker = asker
        self._id = (await self._create_db('SONG', name=format_name(name), url=url))[0]
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
    
    def __str__(self) -> str:
        return f"Song: {self.name} - {self.url}"


class Playlist(DatabaseAccess):
    def __init__(self, copy):
        super().__init__(copy)
        self._id: int | None = None
        self._name: str | None = None
        self._songs: list[Song] | None = None

    @classmethod
    async def from_id(cls, playlist_id: int, is_copy=False) -> 'Playlist':
        self = cls(is_copy)
        self._id = playlist_id
        playlist = await self._get_db('PLAYLIST', 'name', playlist_id=playlist_id)
        if playlist is not None:
            self._name = format_name(playlist[0])
        songs = await self._get_db('PLAYLIST_SONG', 'SONG.name', 'SONG.url', 'ASKER.discord_id', all_results=True,
                                   joins=[JoinCondition('PLAYLIST_SONG', 'SONG', 'song_id', 'song_id'),
                                          JoinCondition('PLAYLIST_SONG', 'ASKER', 'asker', 'asker_id')],
                                   order_by="PLAYLIST_SONG.position", **{"PLAYLIST_SONG.playlist_id": playlist_id})

        self._songs = [await Song.create(name, url, asker) for name, url, asker in songs]
        return self

    @classmethod
    async def create(cls, name: str, songs: list[Song], guild_id) -> 'Playlist':
        self = cls(False)
        self._name = name
        await self._create_db('PLAYLIST', name=format_name(name))
        self._id = (await self._get_db('PLAYLIST', 'playlist_id', name=format_name(name)))[0]
        for song in songs:
            self._songs.append(song)
            await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker.id,
                                  position=len(self._songs))
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
        self._loop.create_task(self._update_db('PLAYLIST', {"name": format_name(value)}, playlist_id=self._id))

    @property
    def songs(self) -> list[Song]:
        return self._songs

    async def add_song(self, song: Song):
        self._songs.append(song)
        await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker,
                              position=len(self._songs))

    async def remove_song(self, song: Song):
        self._songs.remove(song)
        await self._delete_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id)

    def __str__(self) -> str:
        return f"Playlist {self.name}: {', '.join([str(song) for song in self.songs])}"


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
        self._playlists = {await Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
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
    
    def __str__(self) -> str:
        return f"UserPlaylistAccess of {self.user_id}: {', '.join([str(playlist) for playlist in self.playlists])}"


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
    async def get_config(cls, guild_id: int, is_copy=False) -> 'Config':
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
        songs = await self._get_db('QUEUE', 'SONG.name', 'SONG.url', 'ASKER.discord_id', all_results=True,
                                   joins=[JoinCondition('QUEUE', 'SONG', 'song_id', 'song_id'),
                                            JoinCondition('QUEUE', 'ASKER', 'asker', 'asker_id')],
                                   **{"QUEUE.server_id": guild_id})
        self._queue = [await Song.create(name, url, asker) for name, url, asker in songs]
        playlists = await self._get_db('PLAYLIST', 'playlist_id', all_results=True)
        self._playlists = {await Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
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
        await self._create_db('QUEUE', song_id=song.id, server_id=self.guild_id, asker=song.asker.id,
                              position=len(self._queue))

    async def remove_from_queue(self, song: Song):
        self._queue.remove(song)
        await self._delete_db('QUEUE', song_id=song.id, server_id=self.guild_id)

    async def edit_queue(self, new_queue: list[Song]):
        await self.clear_queue()
        for song in new_queue:
            await self.add_to_queue(song)

    async def add_playlist(self, playlist: Playlist):
        self._playlists.add(playlist)
        await self._create_db('PLAYLIST', playlist_id=playlist.id, name=playlist.name)
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

    def __str__(self) -> str:
        return f"Config of {self.guild_id}: {self.loop_song}, {self.loop_queue}, {self.random}, {self.volume}, "\
        f"{self.position},\n{', '.join([str(song) for song in self.queue])},\n{', '.join([str(playlist) for playlist in self.playlists])}"