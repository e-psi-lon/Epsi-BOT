from peewee import (AutoField, 
                    BooleanField, 
                    CharField, 
                    ForeignKeyField, 
                    IntegerField, 
                    Model, 
                    SqliteDatabase, 
                    TextField,
                    OperationalError
                )

from utils.loggers import get_logger

database = SqliteDatabase('./database/database.db')

__all__ = ['Asker', 'Playlist', 'Song', 'PlaylistSong', 'Server', 'Queue', 'ServerPlaylist', 'UserPlaylist', 'get_user_playlists', "BaseModel", "SongListenCount"]

class BaseModel(Model):
    class Meta:
        database = database

    def save(self, force_insert=False, only=None):
        logger = get_logger("Database")
        try:
            out = super().save(force_insert=force_insert, only=only)
            logger.debug(f"Saved {self}")
            return out
        except Exception as e:
            logger.error(f"Error while saving {self}: {e}")


    @classmethod
    def get_or_create_important(cls, important_fields: list[str], **kwargs) -> tuple['BaseModel', bool]:
        importants = {key: kwargs.pop(key) for key in important_fields}
        item = cls.get_or_create(**importants)
        if not item[1]:
            return item
        for key, value in kwargs.items():
            setattr(item[0], key, value)
        item[0].save()
        return item

    def __repr__(self):
        return str(self)
    
    def __str__(self):
        class_name = self.__class__.__name__
        elements = []
        for elem in self._meta.fields:
            try:
                elements.append(f"{elem}={getattr(self, elem)}")
            except OperationalError:
                elements.append(f"{elem}=None")
        return f"{class_name}({', '.join(elements)})"
        

class Asker(BaseModel):
    asker_id = AutoField(null=True, primary_key=True)
    discord_id = IntegerField(null=True)

    class Meta:
        table_name = 'ASKER'

class Playlist(BaseModel):
    name = CharField(null=True)
    playlist_id = AutoField(null=True)

    class Meta:
        table_name = 'PLAYLIST'

    @property
    def songs(self) -> list['PlaylistSong']:
        return PlaylistSong.select().join(Playlist).where(PlaylistSong.playlist == self).order_by(PlaylistSong.position).prefetch(Asker, Song)

class Song(BaseModel):
    name = CharField(null=True)
    song_id = AutoField(null=True, primary_key=True)
    url = TextField(null=True)
    class Meta:
        table_name = 'SONG'

class PlaylistSong(BaseModel):
    asker = ForeignKeyField(column_name='asker', field='asker_id', model=Asker, null=True)
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist, null=True)
    position = IntegerField(null=True)
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song, null=True)

    class Meta:
        table_name = 'PLAYLIST_SONG'
        primary_key = False

class Server(BaseModel):
    loop_queue = BooleanField(null=True)
    loop_song = BooleanField(null=True)
    position = IntegerField(null=True)
    random = BooleanField(null=True)
    server_id = IntegerField(null=True, primary_key=True)
    volume = IntegerField(null=True)

    class Meta:
        table_name = 'SERVER'

    @property
    def queue(self) -> list['Queue']:
        return Queue.select().join(Server).where(Queue.server == self).order_by(Queue.position).prefetch(Asker, Song)

    @queue.setter
    def queue(self, value: list[dict[str, str]]):
        Queue.delete().where(Queue.server == self).execute()
        for position, song in enumerate(value):
            Queue.create(server=self, song=Song.get_or_create(name=song['name'], url=song['url'])[0], position=position, asker=Asker.get_or_create(discord_id=song['asker'])[0])

    @property
    def playlists(self) -> list['ServerPlaylist']:
        return ServerPlaylist.select().join(Server).where(ServerPlaylist.server == self).prefetch(Playlist, Server)

class Queue(BaseModel):
    asker = ForeignKeyField(column_name='asker', field='asker_id', model=Asker, null=True)
    position = IntegerField(null=True)
    server = ForeignKeyField(column_name='server_id', field='server_id', model=Server, null=True)
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song, null=True)

    class Meta:
        table_name = 'QUEUE'
        primary_key = False

class ServerPlaylist(BaseModel):
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist, null=True)
    server = ForeignKeyField(column_name='server_id', field='server_id', model=Server, null=True)

    class Meta:
        table_name = 'SERVER_PLAYLIST'
        primary_key = False



class UserPlaylist(BaseModel):
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist, null=True)
    user = ForeignKeyField(column_name='user_id', field='asker_id', model=Asker, null=True)

    class Meta:
        table_name = 'USER_PLAYLIST'
        primary_key = False

class SongListenCount(BaseModel):
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song, null=True)
    count = IntegerField(default=0)

    class Meta:
        table_name = 'SONG_LISTEN_COUNT'
        primary_key = False

def get_user_playlists(discord_id: int) -> list['UserPlaylist']:
    return UserPlaylist.select().join(Asker).where(UserPlaylist.user.discord_id == discord_id).prefetch(Playlist, Asker)
