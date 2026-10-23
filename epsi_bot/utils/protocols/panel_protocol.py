import datetime
import logging
from asyncio import TimerHandle
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
	from epsi_bot.bot.bot import Bot


class PanelProtocol(Protocol):
	start_time: datetime.datetime | None
	timers: dict[int, TimerHandle]

	bot: Bot
	logger: logging.Logger

	async def shutdown(self) -> None: ...
