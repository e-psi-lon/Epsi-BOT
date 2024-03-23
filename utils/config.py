from typing import Optional, Union, Any
import aiosqlite
import asyncio
from pypika import Table, Query, Field
import logging
from enum import Enum

logger = logging.getLogger("__main__")


def format_name(name: str):
    """Replace |, /, backslash, <, >, :, ;, *, ?, ", and ' with a character with their unicode"""
    return name.replace("|", "u01C0") \
        .replace("/", "u2215") \
        .replace("\\", "u2216") \
        .replace("<", "u003C") \
        .replace(">", "u003E") \
        .replace(":", "u02D0") \
        .replace(";", "u003B") \
        .replace("*", "u2217") \
        .replace("?", "u003F") \
        .replace('"', "u0022") \
        .replace("'", "u0027")


def unformat_name(name: str):
    """Replace unicode characters with |, /, backslash, <, >, :, ;, *, ?, ", and '"""
    return name.replace("u01C0", "|") \
        .replace("u2215", "/") \
        .replace("u2216", "\\") \
        .replace("u003C", "<") \
        .replace("u003E", ">") \
        .replace("u02D0", ":") \
        .replace("u003B", ";") \
        .replace("u2217", "*") \
        .replace("u003F", "?") \
        .replace("u0022", '"') \
        .replace("u0027", "'")


class PlaylistType(Enum):
    """
    A class to represent the type of playlist.
    """
    USER = "User"
    SERVER = "Server"


class JoinCondition:
    """
    A class to represent a join condition in a database query.

    Attributes
    ----------
    first_table : str
        The name of the first table to join.
    second_table : str
        The name of the second table to join.
    first_column : str
        The name of the column of the first table to use to join.
    second_column : str
        The name of the column of the second table to use to join.
    """

    def __init__(self, first_table: str, second_table: str, first_column: str, second_column: str):
        self.first_table = first_table
        self.second_table = second_table
        self.first_column = first_column
        self.second_column = second_column


class DatabaseAccess:
    """
    An abstract class to access the database.
    """

    def __init__(self, copy: bool):
        self._copy = copy
        self._loop = asyncio.get_event_loop()

    async def _song_exists(self, **song_data) -> bool:
        """Check if a song exists in the database."""
        return await self._get_db('SONG', 'song_id', **song_data) is not None

    async def _asker_exists(self, asker_id: int) -> bool:
        """Check if an asker exists in the database."""
        return await self._get_db('ASKER', 'asker_id', asker_id=asker_id) is not None

    async def _get_db(self, table: str, *columns: str, all_results: bool = False,
                      joins: Optional[list[JoinCondition]] = None,
                      create_if_none: bool = False, order_by: Optional[str] = None, **where: Any) \
            -> Optional[Union[list[tuple], tuple]]:
        """
        Get data from the database.

        Parameters
        ----------
        table : str
            The name of the table to get data from.
        columns : str
            The columns to get data from. If columns is `*`, get all the columns.
        all_results : bool
            If True, get all the results. If False, get only the first result. Default is False.
        joins : list[JoinCondition]
            The joins to use in the query. Default is None.
        create_if_none : bool
            If True, create the data if it does not exist. Default is False.
        order_by : str
            The column to order the results by. Default is None.
        where : Any
            The conditions to use in the query.

        Returns
        -------
        Optional[Union[list[tuple], tuple]]
            The results of the query. If all_results is True, return a list of tuples. If all_results is False,
             return a tuple.
        
        Raises
        ------
        sqlite3.Error
            If an error occurs when executing the query.
        """
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            new_table = Table(table)
            query = Query.from_(new_table)
            for key, value in where.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.where(getattr(Table(table_name), column) == value)
                else:
                    query = query.where(getattr(new_table, key) == value)
            if joins is not None:
                for join in joins:
                    table1 = Table(join.first_table)
                    table2 = Table(join.second_table)
                    query = query.join(table2).on(
                        getattr(table1, join.first_column) == getattr(table2, join.second_column))
            if order_by is not None:
                if isinstance(order_by, str):
                    if len(order_by.split('.')) > 1:
                        table_name, column = order_by.split('.')
                        query = query.orderby(Field(column, table=Table(table_name)))
                    else:
                        query = query.orderby(Field(order_by))
                elif isinstance(order_by, list):
                    for column in order_by:
                        if len(column.split('.')) > 1:
                            table_name, column = column.split('.')
                            query = query.orderby(Field(column, table=Table(table_name)))
                        else:
                            query = query.orderby(Field(column))
                else:
                    raise ValueError("order_by must be a string or a list of strings")
            if columns[0] != '*':
                for column in columns:
                    column = column.split('.')
                    if len(column) > 1:
                        if column[1] != '*':
                            query = query.select(getattr(Table(column[0]), column[1]))
                        else:
                            query = query.select(Field('*', table=Table(column[0])))
                    else:
                        query = query.select(getattr(new_table, column[0]))
            else:
                query = query.select("*")
            query = str(query)
            logger.debug(f"Executing query: {query}")
            await cursor.execute(query)
            results = await cursor.fetchall() if all_results else await cursor.fetchone()
            if results is None and create_if_none:
                await self._create_db(table, **where)
                results = await cursor.fetchone()
            return results

    async def _update_db(self, table: str, columns_values: dict[str, str],
                         **where: Any) -> None:
        """
        Update data in the database.

        Parameters
        ----------
        table : str
            The name of the table to update data in.
        columns_values : dict[str, str]
            The columns and their new values.
        where : Any
            The conditions to use in the query.

        Raises
        ------
        sqlite3.Error
            If an error occurs when executing the query.
        """
        if self._copy:
            return
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table = Table(table)
            query = Query.update(table)
            for key, value in columns_values.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.set(Field(column, table=table_name), value)
                else:
                    query = query.set(Field(key, table=table), value)
            for key, value in where.items():
                if len(key.split('.')) > 1:
                    table_name, column = key.split('.')
                    query = query.where(Field(column, table=table_name) == value)
            query = str(query)
            logger.debug(f"Executing query: {query}")
            await cursor.execute(query)
            await conn.commit()

    async def _create_db(self, table, **columns_values: Any) -> Optional[Union[list[tuple], tuple]]:
        """
        Create data in the database.

        Parameters
        ----------
        table : str
            The name of the table to create data in.
        columns_values : dict[str, str]
            The columns and their values.
        
        Returns
        -------
        Optional[Union[list[tuple], tuple]]
            The results of the query. If all_results is True,
            return a list of tuples. If all_results is False, return a tuple.

        Raises
        ------
        sqlite3.Error
            If an error occurs when executing the query.
        """
        if self._copy:
            return await self._get_db(table, f"{table}.*", **columns_values)
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            table_ = Table(table)
            query = Query.into(table_).columns(*columns_values.keys()).insert(*columns_values.values())
            query = str(query)
            logger.debug(f"Executing query: {query}")
            await cursor.execute(query)
            await conn.commit()
        return await self._get_db(table, f"*", **columns_values)

    async def _delete_db(self, table: str, **where: Any) -> None:
        """
        Delete data in the database.

        Parameters
        ----------
        table : str
            The name of the table to delete data in.
        where : Any
            The conditions to use in the query.
        
        Raises
        ------
        sqlite3.Error
            If an error occurs when executing the query.
        """
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
            logger.debug(f"Executing query: {query}")
            await cursor.execute(query)
            await conn.commit()

    async def _custom_query(self, query: str, commit: bool = False, return_results: bool = False,
                            return_all: bool = False):
        """
        Execute a custom query which is not a simple select, update, insert, or delete query.

        Parameters
        ----------
        query : str
            The query to execute.
        commit : bool
            If True, commit the changes. Default is  False.
        return_results : bool
            If True, return the results of the query. Default is False.
        return_all: bool
            If True, return all the results. If False, return only the first result. Useless if return_results is False.
            Default is False.

        Returns
        -------
        Any
            The results of the query. If return_results is True, return the results of the query.
            If return_results is False, return None.
    
        Raises
        ------
        sqlite3.Error
            If an error occurs when executing the query.
        """
        async with aiosqlite.connect("database/database.db") as conn:
            cursor = await conn.cursor()
            logger.debug(f"Executing query: {query}")
            await cursor.execute(query)
            if not self._copy and commit:
                await conn.commit()
            if return_results:
                return await cursor.fetchall() if return_all else await cursor.fetchone()


class Asker(DatabaseAccess):
    """
    A class to represent a user who asked for a song.
    
    Properties
    ----------
    id : int
        The database id of the asker.
    discord_id : int
        The discord id of the asker.
    
    Methods
    -------
    from_id(discord_id: int, is_copy: bool = False) -> Asker (classmethod)
        Get an Asker object from the database.
    """

    def __init__(self, copy=False):
        super().__init__(copy)
        self._id: Optional[int] = None
        self._discord_id: Optional[int] = None

    @classmethod
    async def from_id(cls, discord_id: int, is_copy: bool = False) -> 'Asker':
        """
        Get an Asker object from the database.

        Parameters
        ----------
        discord_id : int
            The id of the user.
        is_copy : bool
            If True, the database will not be modified when modifying the object. Default is False.
        
        Returns
        -------
        Asker
            The Asker object.
        """
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
        """The database id of the asker."""
        return self._id

    @property
    def discord_id(self) -> int:
        """The discord id of the asker."""
        return self._discord_id

    def __str__(self) -> str:
        return f"Asker: {self.discord_id}"


class Song(DatabaseAccess):
    """
    A class to represent a song.

    Properties
    ----------
    id : int
        The database id of the song.
    name : str
        The name of the song.
    title : str
        The title of the song. (Identical to name)
    url : str
        The url of the song.
    asker : Optional[Asker]
        The user who asked for the song. Can be None.
    
    Methods
    -------
    create(name: str, url: str, asker: Asker, is_copy: bool = False) -> Song (classmethod)
        Create a Song object.
    """

    def __init__(self, copy=False):
        super().__init__(copy)
        self._id: Optional[int] = None
        self._name: Optional[str] = None
        self._url: Optional[str] = None
        self._asker: Optional[Asker] = None

    @classmethod
    async def create(cls, name: str, url: str, asker: Asker, is_copy: bool = False) -> 'Song':
        """
        Create a Song object. If the song exists in the database, get the song from the database.
        
        Parameters
        ----------
        name : str
            The name of the song.
        url : str
            The url of the song.
        asker : Asker
            The user who asked for the song.
        is_copy : bool
            If True, the database will not be modified when modifying the object. Default is False.
        
        Returns
        -------
        Song
            The Song object.
        """
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
        """The database id of the song."""
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def name(self) -> str:
        """The name of the song."""
        return self._name

    @property
    def title(self) -> str:
        """The title of the song. (Identical to name)"""
        return self._name

    @property
    def url(self) -> str:
        """The url of the song."""
        return self._url

    @property
    def asker(self) -> Optional[Asker]:
        """The user who asked for the song. Can be None."""
        return self._asker

    def __eq__(self, other) -> bool:
        return isinstance(other, Song) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        return f"Song: {self.name} - {self.url}"


class Playlist(DatabaseAccess):
    """
    A class to represent a playlist.

    Properties
    ----------
    id : int
        The database id of the playlist.
    name : str
        The name of the playlist.
    songs : list[Song]
        The songs in the playlist.
    
    Methods
    -------
    from_id(playlist_id: int, is_copy: bool = False) -> Playlist (classmethod)
        Get a Playlist object from the database.
    create(name: str, songs: list[Song], guild_id: int) -> Playlist (classmethod)
        Create a Playlist object.
    add_song(song: Song) -> None
        Add a song to the playlist.
    remove_song(song: Song) -> None
        Remove a song from the playlist.
    insert_song(song: Song, index: int) -> None
        Insert a song to the playlist at a specific index.
    """

    def __init__(self, copy: bool):
        super().__init__(copy)
        self._id: Optional[int] = None
        self._name: Optional[str] = None
        self._songs: list[Song] = []

    @classmethod
    async def from_id(cls, playlist_id: int, is_copy: bool = False) -> 'Playlist':
        """
        Get a Playlist object from the database.

        Parameters
        ----------
        playlist_id : int
            The id of the playlist.
        is_copy : bool
            If True, the database will not be modified when modifying the object. Default is False.
        
        Returns
        -------
        Playlist
            The Playlist object.
        """
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
    async def create(cls, name: str, songs: list[Song], where_id: int, playlist_type: PlaylistType) -> 'Playlist':
        """
        Create a Playlist object.

        Parameters
        ----------
        name : str
            The name of the playlist.
        songs : list[Song]
            The songs in the playlist.
        where_id : int
            The id of the user or the server.
        playlist_type : PlaylistType
            The type of the playlist. Must be PlaylistType.USER or PlaylistType.SERVER.
        
        Returns
        -------
        Playlist
            The Playlist object.
        
        Raises
        ------
        ValueError
            If the type is not PlaylistType.USER or PlaylistType.SERVER.
        """
        self = cls(False)
        self._name = name
        await self._create_db('PLAYLIST', name=format_name(name))
        self._id = (await self._get_db('PLAYLIST', 'playlist_id', name=format_name(name)))[0]
        for song in songs:
            self._songs.append(song)
            await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker.id,
                                  position=len(self._songs))
        if playlist_type == PlaylistType.USER:
            await self._create_db('USER_PLAYLIST', user_id=where_id, playlist_id=self._id)
        elif playlist_type == PlaylistType.SERVER:
            await self._create_db('SERVER_PLAYLIST', server_id=where_id, playlist_id=self._id)
        else:
            raise ValueError("Invalid type")
        return self

    @property
    def id(self) -> int:
        """The database id of the playlist."""
        return self._id

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._loop.create_task(self._update_db('PLAYLIST', {"name": format_name(value)}, playlist_id=self._id))

    @property
    def songs(self) -> list[Song]:
        """The songs in the playlist."""
        return self._songs

    async def add_song(self, song: Song):
        """Add a song to the playlist."""
        self._songs.append(song)
        await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker.id,
                              position=len(self._songs))

    async def remove_song(self, song: Song):
        """Remove a song from the playlist."""
        index = self._songs.index(song)
        self._songs.remove(song)
        await self._delete_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id)
        table = Table('PLAYLIST_SONG')
        query = Query.update(table).set("position", table.position - 1).where((table.playlist_id == self._id) &
                                                                              (table.position > index))
        await self._custom_query(str(query), commit=True)

    async def insert_song(self, song: Song, index: int):
        """Insert a song to the playlist at a specific index."""
        self._songs.insert(index, song)
        await self._create_db('PLAYLIST_SONG', playlist_id=self._id, song_id=song.id, asker=song.asker.id,
                              position=index)
        table = Table('PLAYLIST_SONG')
        query = Query.update(table).set("position", table.position + 1).where((table.playlist_id == self._id) &
                                                                              (table.position >= index))
        await self._custom_query(str(query), commit=True)

    def __str__(self) -> str:
        return f"Playlist {self.name}: {', '.join([str(song) for song in self.songs])}"


class UserPlaylistAccess(DatabaseAccess):
    """
    A class to represent the access to the playlists of a user. It has the same playlists methods as the Config class.\n
    The only difference is that the playlists are not server specific but user specific.

    Properties
    ----------
    user_id : int
        The id of the user.
    playlists : set[Playlist]
        The playlists of the user.
    
    Methods
    -------
    from_id(user_id: int, is_copy: bool = False) -> UserPlaylistAccess (classmethod)
        Get a UserPlaylistAccess object from the database.
    add_playlist(playlist: Playlist) -> None
        Add a playlist to the user's playlists.
    remove_playlist(playlist: Playlist) -> None
        Remove a playlist from the user's playlists.
    get_playlist(playlist_id) -> Playlist
        Get a playlist from the user's playlists. Search in the database again if the playlist is not in the object.
    """

    def __init__(self, copy: bool):
        super().__init__(copy)
        self._user_id: Optional[int] = None
        self._playlists: set[Playlist] = set()

    @classmethod
    async def from_id(cls, user_id: int, is_copy: bool = False) -> 'UserPlaylistAccess':
        """
        Get a UserPlaylistAccess object from the database.

        Parameters
        ----------
        user_id : int
            The id of the user.
        is_copy : bool
            If True, the database will not be modified when modifying the object. Default is False.

        Returns
        -------
        UserPlaylistAccess
            The UserPlaylistAccess object.
        """
        self = cls(is_copy)
        self._user_id = user_id
        playlists = await self._get_db('PLAYLIST', 'PLAYLIST.playlist_id', all_results=True,
                                       joins=[JoinCondition('USER_PLAYLIST', 'PLAYLIST',
                                                            'playlist_id', 'playlist_id')],
                                       **{"USER_PLAYLIST.user_id": user_id})
        self._playlists = {await Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
        return self

    @property
    def user_id(self) -> int:
        """The id of the user."""
        return self._user_id

    @property
    def playlists(self) -> set[Playlist]:
        """The playlists of the user."""
        return self._playlists

    async def add_playlist(self, playlist: Playlist):
        """Add a playlist to the user's playlists."""
        self._playlists.add(playlist)
        await self._create_db('PLAYLIST', playlist_id=playlist.id, name=playlist.name)
        for song in playlist.songs:
            await self._create_db('PLAYLIST_SONG', playlist_id=playlist.id, song_id=song.id, asker=song.asker.id)

    async def remove_playlist(self, playlist: Playlist):
        """Remove a playlist from the user's playlists."""
        self._playlists.remove(playlist)
        await self._delete_db('PLAYLIST', playlist_id=playlist.id)
        await self._delete_db('PLAYLIST_SONG', playlist_id=playlist.id)
        await self._delete_db('USER_PLAYLIST', user_id=self.user_id, playlist_id=playlist.id)

    async def get_playlist(self, playlist_id):
        """Get a playlist from the user's playlists. Search in the database again if the playlist is not in the
        object."""
        for playlist in self._playlists:
            if playlist.id == playlist_id:
                return playlist
        return await Playlist.from_id(playlist_id, is_copy=self._copy)

    def __str__(self) -> str:
        return f"UserPlaylistAccess of {self.user_id}: {', '.join([str(playlist) for playlist in self.playlists])}"


class Config(DatabaseAccess):
    """
    A class to represent the configuration of a guild.

    Properties
    ----------
    guild_id : int
        The id of the guild.
    loop_song : bool
        If the player should loop around the song.
    loop_queue : bool
        If the player should loop around the queue.
    random : bool
        If the player should play the songs in the queue in a random order.
    volume : int
        The volume of the player.
    position : int
        The position of the song in the queue.
    queue : list[Song]
        The queue of the player.
    playlists : set[Playlist]
        The playlists of the guild.
    
    Methods
    -------
    get_config(guild_id: int, is_copy: bool = False) -> Config (classmethod)
        Get the config of a guild from the database. If the guild does not exist, create it.
    config_exists(guild_id: int) -> bool (staticmethod)
        Check if the guild exists in the database.
    create_config(guild_id: int) -> Config (classmethod)
        Initialize the config of a guild in the database.
    clear_queue() -> None
        Clear the queue.
    add_to_queue(song: Song) -> None
        Add a song to the queue.
    remove_from_queue(song: Song) -> None
        Remove a song from the queue.
    insert_to_queue(song: Song, index: int) -> None
        Insert a song to the queue at a specific index.
    edit_queue(new_queue: list[Song]) -> None
        Replace the actual queue with a new queue.
    add_playlist(playlist: Playlist) -> None
        Add a playlist to the guild's playlists.
    remove_playlist(playlist: Playlist) -> None
        Remove a playlist from the guild's playlists.
    get_playlist(playlist_id) -> Playlist
        Get a playlist from the guild's playlists. Search in the database again if the playlist is not in the object.
    """

    def __init__(self, copy: bool):
        super().__init__(copy)
        self.guild_id: Optional[int] = None
        self._loop_song: Optional[bool] = None
        self._loop_queue: Optional[bool] = None
        self._random: Optional[bool] = None
        self._volume: Optional[int] = None
        self._position: Optional[int] = None
        self._queue: list[Song] = []
        self._playlists: set[Playlist] = set()

    @classmethod
    async def get_config(cls, guild_id: int, is_copy: bool = False) -> 'Config':
        """Get the config of a guild from the database. If the guild does not exist, create it.

        Parameters
        ----------
        guild_id : int
            The id of the guild.
        is_copy : bool
            If True, the database will not be modified when modifying the object. Default is False.
        
        Returns
        -------
        Config
            The config of the guild.
        """
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
        self._queue = [await Song.create(name, url, await Asker.from_id(asker_discord)) for name, url, asker_discord in
                       songs]
        playlists = await self._get_db('PLAYLIST', 'PLAYLIST.playlist_id', all_results=True,
                                       joins=[JoinCondition('SERVER_PLAYLIST', 'PLAYLIST',
                                                            'playlist_id', 'playlist_id')],
                                       **{"SERVER_PLAYLIST.server_id": guild_id})
        self._playlists = {await Playlist.from_id(playlist_id, is_copy=self._copy) for playlist_id in playlists}
        return self

    @staticmethod
    async def config_exists(guild_id):
        """Check if the guild exists in the database."""
        self = Config(True)
        return await self._get_db('SERVER', 'server_id', server_id=guild_id) is not None

    @classmethod
    async def create_config(cls, guild_id):
        """Initialize the config of a guild in the database."""
        self = cls(False)
        self.guild_id = guild_id
        await self._create_db('SERVER', server_id=guild_id, loop_song=False, loop_queue=False, random=False, volume=100,
                              position=0)
        return self

    @property
    def loop_song(self) -> bool:
        """If the player should loop around the song."""
        return self._loop_song

    @loop_song.setter
    def loop_song(self, value):
        self._loop_song = value
        self._loop.create_task(self._update_db('SERVER', {"loop_song": value}, server_id=self.guild_id))

    @property
    def loop_queue(self) -> bool:
        """If the player should loop around the queue."""
        return self._loop_queue

    @loop_queue.setter
    def loop_queue(self, value):
        self._loop_queue = value
        self._loop.create_task(self._update_db('SERVER', {"loop_queue": value}, server_id=self.guild_id))

    @property
    def random(self) -> bool:
        """If the player should play the songs in the queue in a random order."""
        return self._random

    @random.setter
    def random(self, value):
        self._random = value
        self._loop.create_task(self._update_db('SERVER', {"random": value}, server_id=self.guild_id))

    @property
    def volume(self) -> int:
        """The volume of the player. The volume is an integer between 0 and 100."""
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        self._loop.create_task(self._update_db('SERVER', {"volume": value}, server_id=self.guild_id))

    @property
    def position(self) -> int:
        """The position of the song in the queue. The position is 0 for the first song in the queue."""
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self._loop.create_task(self._update_db('SERVER', {"position": value}, server_id=self.guild_id))

    @property
    def queue(self) -> list[Song]:
        """
        A copy of the queue to avoid modifying it outside the class.\n
        Use add_to_queue, remove_from_queue, insert_to_queue, edit_queue to modify the queue.
        """
        return self._queue.copy()

    @property
    def playlists(self) -> set[Playlist]:
        """
        A copy of the playlists to avoid modifying it outside the class.\n
        Use add_playlist, remove_playlist to modify the playlists.
        """
        return self._playlists.copy()

    async def clear_queue(self):
        """Clear the queue."""
        self._queue.clear()
        await self._delete_db('QUEUE', server_id=self.guild_id)

    async def add_to_queue(self, song: Song):
        """Add a song to the queue."""
        self._queue.append(song)
        await self._create_db('QUEUE', song_id=song.id, server_id=self.guild_id, asker=song.asker.id,
                              position=len(self._queue))

    async def remove_from_queue(self, song: Song):
        """Remove a song from the queue."""
        self._queue.remove(song)
        await self._delete_db('QUEUE', song_id=song.id, server_id=self.guild_id)
        table = Table('QUEUE')
        query = Query.update(table).set("position", table.position - 1).where((table.server_id == self.guild_id) &
                                                                              (table.position > self._queue.index(
                                                                                  song)))
        await self._custom_query(str(query), commit=True)

    async def insert_to_queue(self, song: Song, index: int):
        """Insert a song to the queue at a specific index."""
        self._queue.insert(index, song)
        await self._create_db('QUEUE', song_id=song.id, server_id=self.guild_id, asker=song.asker.id, position=index)
        table = Table('QUEUE')
        query = Query.update(table).set("position", table.position + 1).where((table.server_id == self.guild_id) &
                                                                              (table.position >= index))
        await self._custom_query(str(query), commit=True)

    async def edit_queue(self, new_queue: list[Song]):
        """Replace the actual queue with a new queue."""
        await self.clear_queue()
        for song in new_queue:
            await self.add_to_queue(song)

    async def add_playlist(self, playlist: Playlist):
        """Add a playlist to the guild's playlists."""
        self._playlists.add(playlist)

    async def remove_playlist(self, playlist: Playlist):
        """Remove a playlist from the guild's playlists."""
        self._playlists.remove(playlist)
        await self._delete_db('PLAYLIST', playlist_id=playlist.id)
        await self._delete_db('PLAYLIST_SONG', playlist_id=playlist.id)
        await self._delete_db('SERVER_PLAYLIST', server_id=self.guild_id, playlist_id=playlist.id)

    async def get_playlist(self, playlist_id: int):
        """Get a playlist from the guild's playlists. Search in the database again if the playlist is not in the
        object."""
        for playlist in self._playlists:
            if playlist.id == playlist_id:
                return playlist
        return await Playlist.from_id(playlist_id, is_copy=self._copy)

    def __str__(self) -> str:
        return f"Config of {self.guild_id}: {self.loop_song}, {self.loop_queue}, {self.random}, {self.volume}, " \
               f"{self.position},\n{', '.join([str(song) for song in self.queue])},\n{', '.join([str(playlist) for playlist in self.playlists])}"
