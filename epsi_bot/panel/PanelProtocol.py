import datetime
from asyncio import TimerHandle
from typing import Protocol, Any, TypeVar
from aiomultiprocess import Process

from epsi_bot.utils import IPCManager


class PanelProtocol(Protocol):
	bot_process: Process
	start_time: datetime.datetime | None
	timers: dict[int, TimerHandle]

	ipc: IPCManager
	bot_ipc: IPCManager
	async def start_bot(self): ...
	async def stop_bot(self) -> None: ...
	async def get_from_bot(self, command: str, **kwargs: Any) -> Any: ...
	async def post_to_bot(self, command: str, **kwargs: Any) -> None: ...


PanelApp = TypeVar("PanelApp", bound=PanelProtocol)