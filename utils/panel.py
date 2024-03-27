import asyncio
from discord import Guild, Member, User
from discord.abc import GuildChannel
from .config import Song

from typing import Any, Callable, Coroutine, Union
from enum import Enum

class RequestType(Enum):
    GET = 'GET'
    POST = 'POST'

class PanelToBotRequest:
    def __init__(self, type: RequestType, content, **extra):
        self.type = type
        self.content = content
        self.extra = extra

    def __getstate__(self) -> object:
        return self.__dict__
    
    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        return f"Type: {self.type}, Content: {self.content}, Extra data: {self.extra}"


class GuildData:
    def __init__(self, name: str, id: int, icon: str, members: list['MemberData'], channels: list['ChannelData']):
        self.name = name
        self.id = id
        self.icon = icon
        self.members: list[MemberData] = members
        self.channels: list[ChannelData] = channels

    def __getstate__(self) -> object:
        return self.__dict__
    
    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            if getattr(self, key, None) is not None:
                setattr(self, key, value)

    @classmethod
    def from_guild(cls, guild: Guild):
        return cls(
            name=guild.name,
            id=guild.id,
            icon=getattr(guild.icon, "url", ""),
            members=[MemberData.from_member(member) for member in guild.members],
            channels=[ChannelData.from_channel(channel) for channel in guild.channels]
        )
    
    def __str__(self) -> str:
        return str(self.__getstate__())
        


class MemberData:
    def __init__(self, name: str, global_name: str, id: int, avatar: str):
        self.name = name
        self.global_name = global_name
        self.id = id
        self.avatar = avatar

    def __getstate__(self) -> object:
        return self.__dict__
    
    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            if getattr(self, key, None) is not None:
                setattr(self, key, value)

    @classmethod
    def from_member(cls, member: Member):
        return cls(
            name=member.name,
            global_name=member.global_name,
            id=member.id,
            avatar=getattr(member.avatar, "url", "")
        )
    
    def __str__(self) -> str:
        return str(self.__getstate__())


class ChannelData:
    def __init__(self, name: str, id: int, type: str):
        self.name = name
        self.id = id
        self.type = type

    def __getstate__(self) -> object:
        return self.__dict__
    
    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            if getattr(self, key, None) is not None:
                setattr(self, key, value)

    @classmethod
    def from_channel(cls, channel: GuildChannel):
        return cls(
            name=channel.name,
            id=channel.id,
            type=channel.type.name
        )
    
    def __str__(self) -> str:
        return str(self.__getstate__())


class UserData:
    def __init__(self, name: str, global_name: str, id: int, avatar: str):
        self.name = name
        self.global_name = global_name
        self.id = id
        self.avatar = avatar

    def __getstate__(self) -> object:
        return self.__dict__
    
    def __setstate__(self, state: dict) -> None:
        for key, value in state.items():
            if getattr(self, key, None) is not None:
                setattr(self, key, value)

    @classmethod
    def from_user(cls, user: User):
        return cls(
            name=user.name,
            global_name=user.global_name,
            id=user.id,
            avatar=getattr(user.avatar, "url", "")
        )
    
    def __str__(self) -> str:
        return str(self.__getstate__())
    

class ConfigData:
    def __init__(self, loop_song: bool, loop_queue: bool, random: bool, position: int, queue: list[Song], server_id: int, name: str):
        self.loop_song = loop_song
        self.loop_queue = loop_queue
        self.random = random
        self.position = position
        self.queue = queue
        self.id = server_id
        self.name = name

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