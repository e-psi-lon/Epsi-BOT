from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from discord import Guild, User
from discord.abc import GuildChannel

from .config import Song

__all__ = ["RequestType", "PanelToBotRequest", "ChannelData", "UserData", "GuildData", "ConfigData"]


class RequestType(Enum):
    """Enum to represent the type of request from the panel to the bot."""
    GET = 'GET'
    POST = 'POST'


@dataclass
class PanelToBotRequest:
    """Dataclass to represent a request from the panel to the bot.
    
    Attributes
    ----------
    type : RequestType
        The type of request
    content : Any
        The content of the request
    extra : Optional[dict]
        Extra data for the request. Default is an empty dictionary.

    Methods
    -------
    create(type_: RequestType, content: Any, **kwargs) -> PanelToBotRequest (classmethod)
        Class method to create a PanelToBotRequest instance.
    """
    type: RequestType
    content: Any
    extra: Optional[dict] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Type: {self.type}, Content: {self.content}, Extra data: {self.extra}"

    @classmethod
    def create(cls, type_: RequestType, content: Any, **kwargs):
        """Class method to create a PanelToBotRequest instance.
        
        Parameters
        ----------
        type_ : RequestType
            The type of the request
        content : Any
            The content of the request
        **kwargs : dict
            Extra data for the request

        Returns
        -------
        PanelToBotRequest
            The PanelToBotRequest instance
        """
        return cls(type_, content, kwargs)


@dataclass
class ChannelData:
    """Dataclass to represent a discord channel in the panel.
    
    Attributes
    ----------
    name : str
        The name of the channel
    id : int
         The id of the channel
    type : str
        The type of the channel

    Methods
    -------
    from_channel(cls, channel: GuildChannel) -> ChannelData (classmethod)
        Class method to create a ChannelData instance from a discord.abc.GuildChannel instance.
    from_dict(cls, dict_: dict) -> ChannelData (classmethod)
        Class method to create a ChannelData instance from a dictionary.
    """
    name: str
    id: int
    type: str

    @classmethod
    def from_channel(cls, channel: GuildChannel):
        """
        Class method to create a ChannelData instance from a discord.abc.GuildChannel instance.
        
        Parameters
        ----------
        channel : GuildChannel
            The discord channel
            
        Returns
        -------
        ChannelData
            The ChannelData instance
        """
        return cls(
            name=channel.name,
            id=channel.id,
            type=channel.type.name
        )

    @classmethod
    def from_dict(cls, dict_: dict):
        """
        Class method to create a ChannelData instance from a dictionary.

        Parameters
        ----------
        dict_ : dict
            The dictionary containing the channel data

        Returns
        -------
        ChannelData
            The ChannelData instance
        """
        return cls(
            name=dict_["name"],
            id=dict_["id"],
            type=dict_["type"]
        )


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
    def from_user(cls, user: User):
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
            global_name=user.global_name if hasattr(user, "global_name") else user.name,
            id=user.id,
            avatar=getattr(user.avatar, "url", "")
        )

    @classmethod
    def from_api_response(cls, response: dict):
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
            avatar=f"https://cdn.discordapp.com/avatars/{response['id']}/{response['avatar']}.png" if response.get(
                "avatar", None) is not None else ""
        )

    @classmethod
    def from_dict(cls, dict_: dict):
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
            avatar=dict_["avatar"]
        )


@dataclass
class GuildData:
    """Dataclass to represent a discord guild in the panel.

    Attributes
    ----------
    name : str
        The name of the guild
    id : int
        The id of the guild
    icon : str
        The icon's url of the guild
    channels : list[ChannelData]
        The channels of the guild

    Methods
    -------
    from_guild(cls, guild: Guild) -> GuildData (classmethod)
        Class method to create a GuildData instance from a discord.Guild instance.
    from_dict(cls, dict_: dict) -> GuildData (classmethod)
        Class method to create a GuildData instance from a dictionary.
    """
    name: str
    id: int
    icon: str
    channels: list[ChannelData] = field(default_factory=list)

    @classmethod
    def from_guild(cls, guild: Guild):
        """
        Class method to create a GuildData instance from a discord.Guild instance.

        Parameters
        ----------
        guild : Guild
            The discord guild.
        Returns
        -------
        GuildData
            The GuildData instance.
        """
        return cls(
            name=guild.name,
            id=guild.id,
            icon=getattr(guild.icon, "url", ""),
            channels=[ChannelData.from_channel(channel) for channel in guild.channels]
        )

    @classmethod
    def from_dict(cls, dict_: dict):
        """
        Class method to create a GuildData instance from a dictionary.

        Parameters
        ----------
        dict_ : dict
            The dictionary containing the guild data

        Returns
        -------
        GuildData
            The GuildData instance
        """
        return cls(
            name=dict_["name"],
            id=dict_["id"],
            icon=dict_["icon"],
            channels=[ChannelData.from_dict(channel) for channel in dict_["channels"]]
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

    def __init__(self, loop_song: bool, loop_queue: bool, random: bool, position: int, queue: list[Song],
                 server_id: int, name: str):
        self.loop_song = loop_song
        self.loop_queue = loop_queue
        self.random = random
        self.position = position
        self.queue = queue
        self.id = server_id
        self.name = name

    def __getstate__(self) -> object:
        return self.__dict__

    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return str(self.__getstate__())

    def to_dict(self):
        """
        Method to convert the ConfigData instance to a dictionary.
        
        Returns
        -------
        dict
            The dictionary representation of the ConfigData instance.
        """
        return self.__getstate__()
