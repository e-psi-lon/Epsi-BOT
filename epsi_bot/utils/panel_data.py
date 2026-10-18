from dataclasses import dataclass

from discord import User

from epsi_bot.utils.models import Queue


@dataclass
class UserData:
	"""Dataclass to represent a discord user in the panel.

	Attributes
	----------
	name : str
	        The name of the user
	global_name : str
	        The global name of the user
	id : int
	        The id of the user
	avatar : str
	        The avatar's url of the user

	Methods
	-------
	from_user(cls, user: User) -> UserData (classmethod)
	        Class method to create a UserData instance from a discord.User instance.
	from_api_response(cls, response: dict) -> UserData (classmethod)
	        Class method to create a UserData instance from a discord API response.
	from_dict(cls, dict_: dict) -> UserData (classmethod)
	        Class method to create a UserData instance from a dictionary.
	"""

	name: str
	global_name: str
	id: int
	avatar: str

	@classmethod
	def from_user(cls, user: User) -> UserData:
		"""
		Class method to create a UserData instance from a discord.User instance.

		Parameters
		----------
		user : User
		        The discord user

		Returns
		-------
		UserData
		        The UserData instance
		"""
		return cls(
			name=user.name,
			global_name=getattr(user, "global_name", user.name),
			id=user.id,
			avatar=getattr(user.avatar, "url", ""),
		)

	@classmethod
	def from_api_response(cls, response: dict) -> UserData:
		"""
		Class method to create a UserData instance from a discord API response.

		Parameters
		----------
		response : dict
		        The API response

		Returns
		-------
		UserData
		        The UserData instance
		"""
		return cls(
			name=response["username"],
			global_name=response["global_name"],
			id=int(response["id"]),
			avatar=f"https://cdn.discordapp.com/avatars/{response['id']}/{response['avatar']}.png"
			if response.get("avatar")
			else "",
		)

	@classmethod
	def from_dict(cls, dict_: dict) -> UserData:
		"""
		Class method to create a UserData instance from a dictionary.

		Parameters
		----------
		dict_ : dict
		        The dictionary containing the user data

		Returns
		-------
		UserData
		        The UserData instance
		"""
		return cls(
			name=dict_["name"],
			global_name=dict_["global_name"],
			id=dict_["id"],
			avatar=dict_["avatar"],
		)

class ConfigData:
	"""Dataclass to represent a server's bot configuration in the panel.

	Attributes
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

	Methods
	-------
	to_dict(self) -> dict
	        Method to convert the ConfigData instance to a dictionary.
	"""

	def __init__(
		self,
		loop_song: bool,
		loop_queue: bool,
		random: bool,
		position: int,
		queue: list[Queue],
		server_id: int,
		name: str,
		volume: int,
	):
		self.loop_song = loop_song
		self.loop_queue = loop_queue
		self.random = random
		self.position = position
		self.queue = queue
		self.guild_id = server_id
		self.name = name
		self.volume = volume

	def __getstate__(self) -> object:
		return self.__dict__

	def __setstate__(self, state: dict) -> None:
		for key, value in state.items():
			setattr(self, key, value)

	def __str__(self) -> str:
		return str(self.__getstate__())

	def to_dict(self) -> dict:
		"""
		Method to convert the ConfigData instance to a dictionary.

		Returns
		-------
		dict
		        The dictionary representation of the ConfigData instance.
		"""
		return dict(self.__getstate__().__dict__)
