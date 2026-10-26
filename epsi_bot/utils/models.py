from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

from tortoise import (
	BaseDBAsyncClient,
	Model,
	fields,
)
from tortoise.exceptions import IntegrityError, OperationalError
from tortoise.fields.relational import ReverseRelation
from tortoise.transactions import in_transaction
from tortoise.validators import MaxValueValidator, MinValueValidator

from epsi_bot.utils.loggers import get_logger
from epsi_bot.utils.secrets import get_secret

__all__ = [
	"AudioReference",
	"BaseModel",
	"Playlist",
	"PlaylistReference",
	"PlaylistSong",
	"Queue",
	"Server",
	"ServerPlaylist",
	"Song",
	"SongListenCount",
	"User",
	"UserPlaylist",
	"get_db_url",
]

_logger = get_logger("Database")


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

	async def save(
		self,
		using_db: BaseDBAsyncClient | None = None,
		update_fields: Iterable[str] | None = None,
		force_create: bool = False,
		force_update: bool = False,
	) -> None:
		try:
			await super().save(
				using_db=using_db,
				update_fields=update_fields,
				force_create=force_create,
				force_update=force_update,
			)
			_logger.debug("Saved %s", self)
		except IntegrityError:
			raise
		except OperationalError:
			_logger.exception("Error while saving %s: ", self)
			raise

	def _describe(self, *, expand: bool) -> str:
		parts: list[str] = []
		for name in self._meta.fields:
			try:
				value = getattr(self, name)
				if isinstance(value, ReverseRelation):
					value = [repr(v) for v in value] if expand else "<ReverseRelation>"
			except OperationalError:
				value = None
			except TypeError:
				value = "<not serializable>"
			parts.append(f"{name}={value}")
		return f"{type(self).__name__}({', '.join(parts)})"

	def __repr__(self) -> str:
		return self._describe(expand=True)

	def __str__(self) -> str:
		return self._describe(expand=False)

	class Meta:
		abstract = True


class Server(BaseModel):
	"""
	Represents a server configuration and its properties.

	Attributes
	----------
	server_id : fields.BigIntField
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

	server_id = fields.BigIntField(primary_key=True, generated=False)
	loop_queue = fields.BooleanField(default=False)
	loop_song = fields.BooleanField(default=False)
	position = fields.IntField(default=0)
	random = fields.BooleanField(default=False)
	volume = fields.IntField(
		default=100, validators=[MinValueValidator(0), MaxValueValidator(100)]
	)
	queue: fields.ReverseRelation[Queue]
	playlists: fields.ReverseRelation[ServerPlaylist]


class User(BaseModel):
	"""
	Represents a user and their associated data.

	Attributes
	----------
	user_id : fields.BigIntField
			The primary key identifier for the user
	playlists : fields.ReverseRelation
			Associated playlists belonging to the user
	"""

	user_id = fields.BigIntField(primary_key=True, generated=False)
	playlists: fields.ReverseRelation[UserPlaylist]


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
	songs: fields.ReverseRelation[PlaylistSong]


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


class AudioReference(BaseModel):
	"""
	Abstract base class for models that reference a Song and have a position.
	Used by PlaylistSong and Queue.
	"""

	asker: fields.ForeignKeyRelation[User] = fields.ForeignKeyField("models.User")
	position: fields.IntField[int] = fields.IntField()
	song: fields.ForeignKeyRelation[Song] = fields.ForeignKeyField(
		"models.Song", on_delete=fields.CASCADE
	)

	class Meta:
		abstract = True

	def _get_scope_field(self) -> dict[str, Any]:
		"""
		Abstract method to get the scope field for position calculation.
		Must be implemented by subclasses to return the appropriate field
		for filtering when calculating the next position.

		Returns
		-------
		dict[str, Any]
				A dictionary representing the scope field for filtering
		"""
		raise NotImplementedError("Subclasses must implement _get_scope_field()")

	async def save(
		self,
		using_db: BaseDBAsyncClient | None = None,
		update_fields: Iterable[str] | None = None,
		force_create: bool = False,
		force_update: bool = False,
	) -> None:
		async with in_transaction():
			if self.position is None:
				last = await (
					self.__class__.filter(**self._get_scope_field())
					.select_for_update()
					.order_by("-position")
					.first()
				)
				self.position = (last.position if last else 0) + 1
			return await super().save(
				using_db=using_db,
				update_fields=update_fields,
				force_create=force_create,
				force_update=force_update,
			)


class PlaylistReference(BaseModel):
	"""
	Abstract base class for models that reference playlists.
	This pattern allows different entities (servers, users) to reference
	the same playlist without duplicating the playlist itself.

	Attributes
	----------
	playlist : fields.ForeignKeyRelation
			A foreign key reference to the Playlist model
	"""

	playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField(
		"models.Playlist"
	)

	class Meta:
		abstract = True


class PlaylistSong(AudioReference):
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

	playlist: fields.ForeignKeyRelation[Playlist] = fields.ForeignKeyField(
		"models.Playlist", related_name="songs"
	)

	def _get_scope_field(self) -> dict[str, Any]:
		return {"playlist": self.playlist}

	class Meta:
		unique_together = (("playlist", "song"),)
		indexes = [("playlist", "position"), ("song_id",)]  # noqa: RUF012


class Queue(AudioReference):
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

	server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField(
		"models.Server", related_name="queue"
	)

	def _get_scope_field(self) -> dict[str, Any]:
		return {"server": self.server}

	class Meta:
		unique_together = (("server", "song"),)
		indexes = [("server", "position"), ("song_id",)]  # noqa: RUF012


class ServerPlaylist(PlaylistReference):
	"""
	Represents a mapping between a playlist and a server.
	Allows servers to reference playlists without owning them.

	Attributes
	----------
	server : fields.ForeignKeyRelation
			A foreign key reference to the Server model
	"""

	server: fields.ForeignKeyRelation[Server] = fields.ForeignKeyField(
		"models.Server", related_name="playlists", on_delete=fields.CASCADE
	)

	class Meta:
		unique_together = (("playlist", "server"),)


class UserPlaylist(PlaylistReference):
	"""
	Represents a relationship between a user and a playlist.
	Allows users to reference playlists without duplicating them.

	Attributes
	----------
	user : fields.ForeignKeyRelation
			A foreign key relation linking to the associated User
	"""

	user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
		"models.User", related_name="playlists", on_delete=fields.CASCADE
	)

	class Meta:
		unique_together = (("playlist", "user"),)


class SongListenCount(BaseModel):
	"""
	Represents the listen count data associated with a song.

	Attributes
	----------
	song : fields.OneToOneRelation
			Foreign key relation to the Song model
	count : fields.IntField
			Count of how many times the song has been listened to
	"""

	song: fields.OneToOneRelation[Song] = fields.OneToOneField(
		"models.Song", related_name="listen_count"
	)
	count = fields.IntField(default=0, validators=[MinValueValidator(0)])


def _require(name: str) -> str:
	if not (value := get_secret(name)):
		raise ValueError(f"Secret '{name}' is not set")
	return value


def get_db_url() -> str:
	user, password, host, port, name = (
		_require(n) for n in ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME")
	)
	return f"asyncpg://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{name}"
