import datetime
import logging
from asyncio import TimerHandle
from typing import TYPE_CHECKING, cast

from quart import Quart, current_app

if TYPE_CHECKING:
	from epsi_bot.bot.bot import Bot


class PanelBase(Quart):
	start_time: datetime.datetime | None
	timers: dict[int, TimerHandle]

	bot: Bot
	logger: logging.Logger

	async def shutdown(self) -> None: ...


current_panel: PanelBase = cast(PanelBase, cast(Quart, current_app))
