from typing import Any
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

from .loggers import get_logger
from peewee import fn

database = SqliteDatabase('./database/database.db')

__all__ = ['Asker', 'Playlist', 'Song', 'PlaylistSong', 'Server', 'Queue', 'ServerPlaylist', 'UserPlaylist', 'get_user_playlists', "BaseModel", "SongListenCount"]

class BaseModel(Model):
    class Meta:
        database = database

    def save(self: 'BaseModel', force_insert: bool = False, only: Any | None = None) -> Any:
        logger = get_logger("Database")
        try:
            out = super().save(force_insert=force_insert, only=only)
            logger.debug(f"Saved {self}")
            return out
        except Exception as e:
            logger.error(f"Error while saving {self}: {e}")
            return None

    @classmethod
    def get_or_create_important(cls: 'BaseModel', important_fields: list[str], **kwargs: Any) -> tuple['BaseModel', bool]:
        importants = {key: kwargs.pop(key) for key in important_fields}
        item, created = cls.get_or_create(**importants)
        if not created:
            return item, created
        for key, value in kwargs.items():
            setattr(item, key, value)
        item.save()
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
        

class Asker(BaseModel):
    asker_id = AutoField(primary_key=True)
    discord_id = IntegerField(unique=True)

    class Meta:
        table_name = 'ASKER'

class Playlist(BaseModel):
    name = CharField()
    playlist_id = AutoField()

    class Meta:
        table_name = 'PLAYLIST'

    @property
    def songs(self) -> list['PlaylistSong']:
        return PlaylistSong.select().join(Playlist).where(PlaylistSong.playlist == self).order_by(PlaylistSong.position).prefetch(Asker, Song)

class Song(BaseModel):
    name = CharField()
    song_id = AutoField(primary_key=True)
    url = TextField(unique=True)
    class Meta:
        table_name = 'SONG'

class PlaylistSong(BaseModel):
    asker = ForeignKeyField(column_name='asker', field='asker_id', model=Asker)
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist)
    position = IntegerField()
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song)

    class Meta:
        table_name = 'PLAYLIST_SONG'
        primary_key = False

    def save(self, *args: Any, **kwargs: Any) -> Any:
        if self.position is None:
            max_position = (
                PlaylistSong
                .select(fn.MAX(PlaylistSong.position))
                .where(PlaylistSong.playlist == self.playlist)
                .scalar() or 0
            )
            self.position = max_position + 1
        return super().save(*args, **kwargs)

class Server(BaseModel):
    loop_queue = BooleanField(default=False)
    loop_song = BooleanField(default=False)
    position = IntegerField(default=0)
    random = BooleanField(default=False)
    server_id = IntegerField(primary_key=True)
    volume = IntegerField(default=100)

    class Meta:
        table_name = 'SERVER'

    @property
    def queue(self) -> list['Queue']:
        return Queue.select().join(Server).where(Queue.server == self).order_by(Queue.position).prefetch(Asker, Song)

    @queue.setter
    def queue(self, value: list[dict[str, str]]) -> None:
        with database.atomic():
            # Get existing queue entries
            existing_queue = {q.position: q for q in Queue.select().where(Queue.server == self)}
            
            # Prepare batch data
            songs_to_create = []
            askers_to_create = []
            queue_to_create = []
            queue_to_update = []
            
            # Process new queue items
            for position, song_data in enumerate(value):
                # Prepare song and asker data
                songs_to_create.append({'name': song_data['name'], 'url': song_data['url']})
                askers_to_create.append({'discord_id': song_data['asker']})
                
                if position in existing_queue:
                    queue_to_update.append(existing_queue[position])
                else:
                    queue_to_create.append(position)
            
            # Batch create songs and askers, using URL and discord_id as conflict fields
            songs = Song.insert_many(songs_to_create).on_conflict(
                conflict_target=[Song.url],
                preserve=[Song.url]
            ).execute()
            askers = Asker.insert_many(askers_to_create).on_conflict(
                conflict_target=[Asker.discord_id],
                preserve=[Asker.discord_id]
            ).execute()
            
            # Get created/existing songs and askers
            songs = {(s.name, s.url): s for s in Song.select().where(Song.url.in_([s['url'] for s in songs_to_create]))}
            askers = {a.discord_id: a for a in Asker.select().where(Asker.discord_id.in_([a['discord_id'] for a in askers_to_create]))}
            
            # Batch update existing entries
            for queue_entry in queue_to_update:
                song_data = value[queue_entry.position]
                queue_entry.song = songs[(song_data['name'], song_data['url'])]
                queue_entry.asker = askers[song_data['asker']]
            if queue_to_update:
                Queue.bulk_update(queue_to_update, fields=['song', 'asker'])
            
            # Batch create new entries
            if queue_to_create:
                Queue.insert_many([{
                    'server': self,
                    'song': songs[(value[pos]['name'], value[pos]['url'])],
                    'position': pos,
                    'asker': askers[value[pos]['asker']]
                } for pos in queue_to_create]).execute()
            
            # Delete entries not in new queue
            positions_to_keep = set(range(len(value)))
            Queue.delete().where(
                (Queue.server == self) & 
                (Queue.position.not_in(positions_to_keep))
            ).execute()

    @property
    def playlists(self) -> list['ServerPlaylist']:
        return ServerPlaylist.select().join(Server).where(ServerPlaylist.server == self).prefetch(Playlist, Server)

class Queue(BaseModel):
    asker = ForeignKeyField(column_name='asker', field='asker_id', model=Asker)
    position = IntegerField()
    server = ForeignKeyField(column_name='server_id', field='server_id', model=Server)
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song)

    class Meta:
        table_name = 'QUEUE'
        primary_key = False

    def save(self, *args, **kwargs) -> Any:
        if self.position is None:
            max_position = (
                Queue
                .select(fn.MAX(Queue.position))
                .where(Queue.server == self.server)
                .scalar() or 0
            )
            self.position = max_position + 1
        return super().save(*args, **kwargs)

class ServerPlaylist(BaseModel):
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist)
    server = ForeignKeyField(column_name='server_id', field='server_id', model=Server)

    class Meta:
        table_name = 'SERVER_PLAYLIST'
        primary_key = False



class UserPlaylist(BaseModel):
    playlist = ForeignKeyField(column_name='playlist_id', field='playlist_id', model=Playlist)
    user = ForeignKeyField(column_name='user_id', field='asker_id', model=Asker)

    class Meta:
        table_name = 'USER_PLAYLIST'
        primary_key = False

class SongListenCount(BaseModel):
    song = ForeignKeyField(column_name='song_id', field='song_id', model=Song)
    count = IntegerField(default=0)

    class Meta:
        table_name = 'SONG_LISTEN_COUNT'
        primary_key = False

def get_user_playlists(user_id: int) -> list['UserPlaylist']:
    return UserPlaylist.select().join(Asker).where(Asker.discord_id == user_id).prefetch(Playlist)

