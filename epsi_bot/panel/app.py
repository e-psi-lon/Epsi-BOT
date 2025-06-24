import asyncio
import datetime
import logging
import os
from asyncio import TimerHandle
from typing import Any, Optional

import discord
from aiomultiprocess import Process  # type: ignore[import-untyped]
from quart import Quart
from quart_session import Session  # type: ignore[import-untyped]
from tortoise import Tortoise
from tortoise.contrib.quart import register_tortoise

from epsi_bot.bot.bot import start, Bot
from epsi_bot.utils import get_logger, parse_args, IPCManager
from epsi_bot.utils.models import get_db_url
from epsi_bot.panel.config import config
from epsi_bot.panel.routes import register_blueprints
from epsi_bot.panel.helpers import register_error_handlers


class Panel(Quart):
	def __init__(self, config_name: str = 'default', *args: Any, **kwargs: Any) -> None:
		super().__init__(__name__, *args, **kwargs)

		# Load configuration
		self.config.from_object(config[config_name])
		config[config_name].init_app(self)

		# Initialize components
		self.bot_process: Optional[Process] = None
		self.start_time: Optional[datetime.datetime] = None
		self.timers: dict[int, TimerHandle] = {}

		# IPC setup
		self.ipc, self.bot_ipc = IPCManager.create_pair()
		self.handle = self.ipc.handle
		self.get_from_bot = self.ipc.request
		self.post_to_bot = self.ipc.send
		self._logger: logging.Logger | None = None

		# Session and database setup
		Session(self)
		register_tortoise(
			self,
			db_url=get_db_url(),
			modules={'models': ['epsi_bot.utils.models']}
		)

		# Register routes and error handlers
		register_blueprints(self)
		register_error_handlers(self)

		# Register IPC handlers
		self._register_ipc_handlers()

	@property
	def logger(self) -> logging.Logger:
		if self._logger is None:
			self._logger = get_logger("Panel", parse_args().log_level.upper())
		return self._logger

	def set_start_time(self, start_time: datetime.datetime) -> None:
		self.start_time = start_time

	async def start_bot(self) -> None:
		bot = Bot(self.bot_ipc, intents=discord.Intents.all())
		if self.start_time is not None:
			await start(bot, self.start_time)
		else:
			raise RuntimeError("Start time not set")

	async def startup(self) -> None:
		# Database initialization
		if not os.path.exists("database/database.db"):
			if not os.path.exists("database/"):
				os.mkdir("database/")
			with open("database/database.db", "w") as f:
				f.write("")
			await Tortoise.init(
				db_url=get_db_url(),
				modules={'models': ['epsi_bot.utils.models']}
			)
			await Tortoise.generate_schemas(safe=True)

		# Start bot process
		self.bot_process = Process(target=self.start_bot, name="Bot")
		await self.ipc.start()
		self.bot_process.start()
		return await super().startup()

	def run(self,
	        host: str | None = None,
	        port: int | None = None,
	        debug: bool | None = None,
	        use_reloader: bool = True,
	        loop: asyncio.AbstractEventLoop | None = None,
	        ca_certs: str | None = None,
	        certfile: str | None = None,
	        keyfile: str | None = None,
	        **kwargs: Any) -> None:
		if debug is None:
			debug = parse_args().log_level.upper() == "DEBUG"
		super().run(host=host, port=port, debug=debug, **kwargs)

	def _register_ipc_handlers(self) -> None:
		@self.ipc.handle("stop")
		async def shutdown(_: str) -> None:
			if self.bot_process:
				await self.bot_process.join()
			await Tortoise.close_connections()
			await self.shutdown()
			exit(0)


def create_app(config_name: str = 'default') -> Panel:
	"""Application factory."""
	return Panel(config_name)