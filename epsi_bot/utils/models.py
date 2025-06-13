from os import getenv
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Iterable, Type

from aiosqlite import OperationalError
from tortoise import (
	BaseDBAsyncClient,
	connections,
	fields,
	Model,
	Tortoise,
	models,
	exceptions,
)
from tortoise.exceptions import NoValuesFetched
from tortoise.fields.relational import ReverseRelation
from tortoise.transactions import in_transaction
from tortoise.validators import MinValueValidator, MaxValueValidator

import epsi_bot.utils
from epsi_bot.utils.loggers import get_logger

# database = SqliteDatabase('./database/database.db')

__all__ = ['User', 'Playlist', 'Song', 'PlaylistSong', 'Server', 'Queue', 'ServerPlaylist', 'UserPlaylist',
           "BaseModel", "SongListenCount", "database_context", "get_db_url"]


class BaseModel(Model):
	"""
	BaseModel class that extends the functionality of the default Model class.
	It provides additional features such as automatic timestamp management,
	advanced save operations with error logging,
	and utilities for creating or retrieving important objects. Elements can be
	represented through repr() for ReverseRelation support and str() otherwise.
	
	Attributes
	----------
	created_at : fields.DatetimeField
		Automatically sets the creation timestamp when an object is first created
	updated_at : fields.DatetimeField
		Automatically updates the timestamp whenever an object is modified
	"""
	created_at = fields.DatetimeField(auto_now_add=True)
	updated_at = fields.DatetimeField(auto_now=True)

	async def save(self, using_db: BaseDBAsyncClient | None = None, update_fields: Iterable[str] | None = None,
	               force_create: bool = False, force_update: bool = False) -> None:
		logger = get_logger("Database")
		try:
			await super().save(using_db=using_db, update_fields=update_fields, force_create=force_create,
			                   force_update=force_update)
			logger.debug(f"Saved {self}")
		except Exception as e:
			logger.error(f"Error while saving {self}: {e}")

	@classmethod
	async def get_or_create_important(cls: Type[models.MODEL], important_fields: list[str], **kwargs: Any) -> tuple[
		models.MODEL, bool]:
		"""
	    Class method to retrieve an existing object or create a new one based on specified important fields.

	    Parameters
	    ----------
	    important_fields : list[str]
	        List of field names that are considered important for uniqueness checking
	    **kwargs : Any
	        Additional field values to use for object creation or retrieval

	    Returns
	    -------
	    tuple[models.MODEL, bool]
	        A tuple containing the retrieved or created object and a boolean indicating
	        whether the object was created (True) or retrieved (False)
		"""
		importants = {key: kwargs.pop(key) for key in important_fields}

		# First try to get existing
		try:
			item = await cls.get(**importants)
			return item, False
		except exceptions.DoesNotExist:
			# Create new with all fields at once
			create_data = {**importants, **kwargs}
			item = await cls.create(**create_data)
			return item, True

	def __repr__(self) -> str:
		class_name = self.__class__.__name__
		elements = []
		for elem in self._meta.fields:
			try:
				element = getattr(self, elem)
				if isinstance(element, ReverseRelation):
					try:
						element = [repr(elem) for elem in element]
						elements.append(f"{elem}={element}")
					except NoValuesFetched:
						elements.append(f"{elem}=None")
				else:
					elements.append(f"{elem}={getattr(self, elem)}")
			except OperationalError:
				elements.append(f"{elem}=None")
			except TypeError:
				elements.append(f"{elem}=<not serializable>")
		return f"{class_name}({', '.join(elements)})"

	def __str__(self) -> str:
		class_name = self.__class__.__name__
		elements = []
		for elem in self._meta.fields:
			try:
				element = getattr(self, elem)
				if isinstance(element, ReverseRelation):
					elements.append(f"{elem}=<ReverseRelation>")
				else:
					elements.append(f"{elem}={getattr(self, elem)}")
			except OperationalError:
				elements.append(f"{elem}=None")
			except TypeError:
				elements.append(f"{elem}=<not serializable>")
		return f"{class_name}({', '.join(elements)})"

	class Meta:
		abstract = True


class User(BaseModel):
	"""
	Represents a user and their associated data.
	
	Attributes
	----------
	user_id : fields.IntField
		The primary key identifier for the user
	discord_id : fields.BigIntField
		Unique Discord identifier for the user
	playlists : fields.ReverseRelation
		Associated playlists belonging to the user
	"""
	user_id = fields.IntField(primary_key=True)
	discord_id = fields.BigIntField(unique=True)
	playlists: fields.ReverseRelation['UserPlaylist']


class Playlist(BaseModel):
	"""
	Represents a playlist entity in the application.
	
	Attributes
	----------
	playlist_id : fields.IntField
		The primary key identifier for the playlist
	name : fields.CharField
		The name of the playlist, with a maximum length of 100 characters
	songs : fields.ReverseRelation
		Reverse relation that links the playlist to its associated songs
	"""
	playlist_id = fields.IntField(primary_key=True)
	name = fields.CharField(100)
	songs: fields.ReverseRelation['PlaylistSong']


class Song(BaseModel):
	"""
	Represents a Song entity with attributes for song ID, name, and URL.
	
	Attributes
	----------
	song_id : fields.IntField
		The primary key identifier for the song
	name : fields.CharField
		The name of the song, with a maximum length of 100 characters
	url : fields.CharField
		The unique URL of the song, with a maximum length of 200 characters
	"""
	song_id = fields.IntField(primary_key=True)
	name = fields.CharField(100)
	url = fields.CharField(200, unique=True)


class PlaylistSong(BaseModel):
	"""
	Represents a song entry within a playlist.
	Extends the save method to automatically calculate position when not provided.
	
	Attributes
	----------
	asker : fields.ForeignKeyRelation
		Link to the User who added the song
	playlist : fields.ForeignKeyRelation
		Link to the associated playlist
	position : fields.IntField
		The song's position within the playlist
	song : fields.ForeignKeyRelation
		Link to the associated song
	"""
	asker: fields.ForeignKeyRelation[User] = fields.ForeignKeyField('models.User')
	playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist', related_name='songs')
	position = fields.IntField()
	song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song')

	async def save(self, using_db: BaseDBAsyncClient | None = None, update_fields: Iterable[str] | None = None,
	               force_create: bool = False, force_update: bool = False) -> None:
		async with in_transaction():
			if self.position is None:
				values = await PlaylistSong.filter(playlist=self.playlist)
				max_position = max([value.position for value in values], default=0)
				self.position = max_position + 1
			return await super().save(using_db=using_db, update_fields=update_fields,
			                          force_create=force_create, force_update=force_update)

	class Meta:
		unique_together = (('playlist', 'song', 'position'),)
		indexes = [
			("playlist_id", "position"),
			("song_id",)
		]


class Server(BaseModel):
	"""
	Represents a server configuration and its properties.
	
	Attributes
	----------
	server_id : fields.IntField
		The primary key identifier for the server
	loop_queue : fields.BooleanField
		Flag indicating if queue looping is enabled
	loop_song : fields.BooleanField
		Flag indicating if song looping is enabled
	position : fields.IntField
		Current position in the queue
	random : fields.BooleanField
		Flag indicating if random mode is enabled
	volume : fields.IntField
		Current volume level (0-100)
	queue : fields.ReverseRelation
		Associated queue entries for the server
	playlists : fields.ReverseRelation
		Associated playlists for the server
	"""
	server_id = fields.BigIntField(primary_key=True)
	loop_queue = fields.BooleanField(default=False)
	loop_song = fields.BooleanField(default=False)
	position = fields.IntField(default=0)
	random = fields.BooleanField(default=False)
	volume = fields.IntField(default=100, validators=[
		MinValueValidator(0),
		MaxValueValidator(100)
	])
	queue: fields.ReverseRelation['Queue']
	playlists: fields.ReverseRelation['ServerPlaylist']


class Queue(BaseModel):
	"""
	Represents a Queue model to manage song requests within a server.
	Extends the save method to automatically calculate position when not provided.
	
	Attributes
	----------
	asker : fields.ForeignKeyRelation
		The user who requested the song
	position : fields.IntField
		The position of the song within the queue
	server : fields.ForeignKeyRelation
		The server to which the queue belongs
	song : fields.ForeignKeyRelation
		The song associated with the queued entry
	"""
	asker: fields.ForeignKeyRelation[User] = fields.ForeignKeyField('models.User')
	position = fields.IntField()
	server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField('models.Server', related_name='queue')
	song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song', on_delete=fields.CASCADE)

	async def save(self, using_db: BaseDBAsyncClient | None = None, update_fields: Iterable[str] | None = None,
	               force_create: bool = False, force_update: bool = False) -> None:
		async with in_transaction():
			if self.position is None:
				values = await Queue.filter(server=self.server)
				max_position = max([value.position for value in values], default=0)
				self.position = max_position + 1
			return await super().save(using_db=using_db, update_fields=update_fields,
			                          force_create=force_create, force_update=force_update)

	class Meta:
		unique_together = (('server', 'song', 'position'),)
		indexes = [
			("server_id", "position")
		]


class ServerPlaylist(BaseModel):
	"""
	Represents a mapping between a playlist and a server.
	
	Attributes
	----------
	playlist : fields.ForeignKeyRelation
		A foreign key reference to the Playlist model
	server : fields.ForeignKeyRelation
		A foreign key reference to the Server model
	"""
	playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist')
	server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField('models.Server', related_name='playlists',
	                                                                   on_delete=fields.CASCADE)

	class Meta:
		unique_together = (('playlist', 'server'),)


class UserPlaylist(BaseModel):
	"""
	Represents a relationship between a user and a playlist.
	
	Attributes
	----------
	playlist : fields.ForeignKeyRelation
		A foreign key relation linking to the associated Playlist
	user : fields.ForeignKeyRelation
		A foreign key relation linking to the associated User
	"""
	playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField('models.Playlist')
	user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField('models.User', related_name='playlists',
	                                                               on_delete=fields.CASCADE)

	class Meta:
		unique_together = (('playlist', 'user'),)


class SongListenCount(BaseModel):
	"""
	Represents the listen count data associated with a song.
	
	Attributes
	----------
	song : fields.ForeignKeyRelation
		Foreign key relation to the Song model
	count : fields.IntField
		Count of how many times the song has been listened to
	"""
	song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField('models.Song', related_name='listen_count',
	                                                               unique=True)
	count = fields.IntField(default=0, validators=[MinValueValidator(0)])


@asynccontextmanager
async def database_context() -> AsyncGenerator[None, None]:
	"""
	Provides an asynchronous context manager for interacting with the Tortoise-ORM database.
	"""
	logger = get_logger("Database")
	try:
		await Tortoise.init(
			db_url=get_db_url(),
			modules={'models': [epsi_bot.utils.models]}
		)
		await Tortoise.generate_schemas(safe=True)
		yield
	except exceptions.BaseORMException as e:
		logger.error(f"Error while accessing database: {e}")
	finally:
		await connections.close_all()
		logger.debug("Tortoise-ORM shutdown")

def get_db_url() -> str:
	"""
	Returns the database URL for the Tortoise-ORM configuration.

	Returns
	-------
	str
		The database URL for the Tortoise-ORM configuration
	"""
	# Load everything from the environment variables
	return f'mysql://{getenv("DB_USER")}:{getenv("DB_PASSWORD")}@{getenv("DB_HOST")}:{getenv("DB_PORT")}/epsi_bot'