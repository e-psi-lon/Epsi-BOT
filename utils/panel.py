import asyncio
from dataclasses import dataclass, field
from discord import Guild, Member, User
from discord.abc import GuildChannel
from .config import Song

from typing import Callable, Union, Any, Optional
from enum import Enum


class RequestType(Enum):
    GET = 'GET'
    POST = 'POST'

@dataclass
class PanelToBotRequest:
    type: RequestType
    content: Any
    extra: Optional[dict] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Type: {self.type}, Content: {self.content}, Extra data: {self.extra}"
    
    @classmethod
    def create(self, type_: RequestType, content: Any, **kwargs):
        return PanelToBotRequest(type_, content, kwargs)
    


@dataclass
class ChannelData:
    name: str
    id: int
    type: str


    @classmethod
    def from_channel(cls, channel: GuildChannel):
        return cls(
            name=channel.name,
            id=channel.id,
            type=channel.type.name
        )
    
    @classmethod
    def from_dict(cls, dict_: dict):
        return cls(
            name=dict_["name"],
            id=dict_["id"],
            type=dict_["type"]
        )
    


@dataclass
class UserData:
    name: str
    global_name: str
    id: int
    avatar: str

    @classmethod
    def from_user(cls, user: User):
        return cls(
            name=user.name,
            global_name=user.global_name,
            id=user.id,
            avatar=getattr(user.avatar, "url", "")
        )
    
    @classmethod
    def from_api_response(cls, response: dict):
        return cls(
            name=response["username"],
            global_name=response["global_name"],
            id=int(response["id"]),
            avatar = f"https://cdn.discordapp.com/avatars/{response['id']}/{response['avatar']}.png" if response.get("avatar", None) is not None else ""
        )
    
    @classmethod
    def from_dict(cls, dict_: dict):
        return cls(
            name=dict_["name"],
            global_name=dict_["global_name"],
            id=dict_["id"],
            avatar=dict_["avatar"]
        )


@dataclass
class GuildData:
    name: str
    id: int
    icon: str
    channels: list[ChannelData] = field(default_factory=list)

    @classmethod
    def from_guild(cls, guild: Guild):
        return cls(
            name=guild.name,
            id=guild.id,
            icon=getattr(guild.icon, "url", ""),
            channels=[ChannelData.from_channel(channel) for channel in guild.channels]
        )
    
    @classmethod
    def from_dict(cls, dict_: dict):
        return cls(
            name=dict_["name"],
            id=dict_["id"],
            icon=dict_["icon"],
            channels=[ChannelData.from_dict(channel) for channel in dict_["channels"]]
        )
    
    


class ConfigData:
    def __init__(self, loop_song: bool, loop_queue: bool, random: bool, position: int, queue: list[Song], server_id: int, name: str):
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
        return self.__getstate__()
    
    


class AsyncTimer:
    def __init__(self, delay: Union[int, float], callback: Callable, *args, **kwargs):
        self.delay = delay
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.task = None

    async def _job(self):
        await asyncio.sleep(self.delay)
        if asyncio.iscoroutinefunction(self.callback):
            await self.callback(*self.args, **self.kwargs)
        else:
            self.callback(*self.args, **self.kwargs)
            
        

    def start(self):
        self.task = asyncio.create_task(self._job())

    def cancel(self):
        if self.task:
            self.task.cancel()
            self.task = None
