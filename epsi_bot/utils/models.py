from typing import Any, AsyncGenerator, Iterable, Type
from aiosqlite import OperationalError
from tortoise import (
                    BaseDBAsyncClient,
                    fields, 
                    Model,
                    Tortoise,
                    models,
                    exceptions,   
                )

from .loggers import get_logger
from contextlib import asynccontextmanager

# database = SqliteDatabase('./database/database.db')

__all__ = ['Asker', 'Playlist', 'Song', 'PlaylistSong', 'Server', 'Queue', 'ServerPlaylist', 'UserPlaylist', "BaseModel", "SongListenCount", "database_context"]
__models__ = list(set(__all__) - {'BaseModel', 'database_context'})

class BaseModel(Model):
    async def save(self, using_db: BaseDBAsyncClient | None = None, update_fields: Iterable[str] | None = None, force_create: bool = False, force_update: bool = False) -> None:
        logger = get_logger("Database")
        try:
            await super().save(using_db=using_db, update_fields=update_fields, force_create=force_create, force_update=force_update)
            logger.debug(f"Saved {self}")
        except Exception as e:
            logger.error(f"Error while saving {self}: {e}")

    @classmethod
    async def get_or_create_important(cls: Type[models.MODEL], important_fields: list[str], **kwargs: Any) -> tuple[models.MODEL, bool]:
        importants = {key: kwargs.pop(key) for key in important_fields}
        item, created = await cls.get_or_create(**importants)
        if not created:
            return item, created
        for key, value in kwargs.items():
            setattr(item, key, value)
        await item.save()
        return item, created

    def __repr__(self) -> str:
        return str(self)
    
    def __str__(self) -> str:
        class_name = self.__class__.__name__
        elements = []
        for elem in self._meta.fields:
            try:
                elements.append(f"{elem}={getattr(self, elem)}")
            except OperationalError:
                elements.append(f"{elem}=None")
            except TypeError:
                elements.append(f"{elem}=<not serializable>")
        return f"{class_name}({', '.join(elements)})"
    
    class Meta:
        abstract = True
        

class Asker(BaseModel):
    asker_id = fields.IntField(primary_key=True)
    discord_id = fields.IntField(unique=True)
    playlists: fields.ReverseRelation['UserPlaylist']

    class Meta:
        table = 'ASKER'

class Playlist(BaseModel):
    name = fields.CharField(100)
    playlist_id = fields.IntField(primary_key=True)
    songs: fields.ReverseRelation['PlaylistSong']

    class Meta:
        table = 'PLAYLIST'


class Song(BaseModel):
    name = fields.CharField(100)
    song_id = fields.IntField(primary_key=True)
    url = fields.CharField(200, unique=True)
    class Meta:
        table = 'SONG'

class PlaylistSong(BaseModel):
    asker: fields.ForeignKeyRelation[Asker] = fields.ForeignKeyField('models.Asker')
    playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist', related_name='playlist_songs')
    position = fields.IntField()
    song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song')

    class Meta:
        table = 'PLAYLIST_SONG'

    async def save(self, *args: Any, **kwargs: Any) -> Any:
        if self.position is None:
            values = await PlaylistSong.filter(playlist=self.playlist)
            max_position = max([value.position for value in values], default=0)
            self.position = max_position + 1
        return await super().save(*args, **kwargs)

class Server(BaseModel):
    loop_queue = fields.BooleanField(default=False)
    loop_song = fields.BooleanField(default=False)
    position = fields.IntField(default=0)
    random = fields.BooleanField(default=False)
    server_id = fields.IntField(primary_key=True)
    volume = fields.IntField(default=100)
    queue: fields.ReverseRelation['Queue']
    playlists: fields.ReverseRelation['ServerPlaylist']

    class Meta:
        table = 'SERVER'

class Queue(BaseModel):
    asker: fields.ForeignKeyRelation[Asker] = fields.ForeignKeyField('models.Asker')
    position = fields.IntField()
    server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField('models.Server')
    song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song')

    class Meta:
        table = 'QUEUE'

    async def save(self, *args: Any, **kwargs: Any) -> Any:
        if self.position is None:
            values = await Queue.filter(server=self.server)
            max_position = max([value.position for value in values], default=0)
            self.position = max_position + 1
        return await super().save(*args, **kwargs)

class ServerPlaylist(BaseModel):
    playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist')
    server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField('models.Server')

    class Meta:
        table = 'SERVER_PLAYLIST'



class UserPlaylist(BaseModel):
    playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist')
    user: fields.ForeignKeyRelation[Asker] = fields.ForeignKeyField('models.Asker', related_name='playlists')

    class Meta:
        table = 'USER_PLAYLIST'

class SongListenCount(BaseModel):
    song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song', related_name='listen_count')
    count = fields.IntField(default=0)

    class Meta:
        table = 'SONG_LISTEN_COUNT'

@asynccontextmanager
async def database_context() -> AsyncGenerator[None, None]:
    """
    Async context manager for database operations.
    
    Yields
    ------
    None
        Context manager doesn't yield any value.
    """
    try:
        await Tortoise.init(
            db_url='sqlite://database/database.db',
            modules={'models': ['epsi_bot.utils.models']}
        )
        await Tortoise.generate_schemas(safe=True)
        yield
    except exceptions.BaseORMException as e:
        logger = get_logger("Database")
        logger.error(f"Error while accessing database: {e}")
    finally:
        await Tortoise.close_connections()