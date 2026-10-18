import asyncio
import datetime
import logging
from asyncio import TimerHandle
from typing import TYPE_CHECKING, Any

from quart import Quart
from quart_session import Session  # type: ignore[import-untyped]

if TYPE_CHECKING:
	from epsi_bot.bot.bot import Bot
from epsi_bot.panel.config import config
from epsi_bot.panel.helpers import register_error_handlers
from epsi_bot.panel.routes import register_blueprints
from epsi_bot.utils.loggers import get_logger, parse_args


class Panel(Quart):
	def __init__(self, config_name: str = "default", *args: Any, **kwargs: Any) -> None:
		super().__init__(__name__, *args, **kwargs)

		# Load configuration
		self.config.from_object(config[config_name])
		config[config_name].init_app(self)

		# Initialize components
		self.bot: Bot | None = None
		self.start_time: datetime.datetime | None = None
		self.timers: dict[int, TimerHandle] = {}

		self._logger: logging.Logger | None = None

		# Session and database setup
		Session(self)
		# Register routes and error handlers
		register_blueprints(self)
		register_error_handlers(self)

		@self.route("/health")
		async def health_check() -> tuple[dict[str, str], int]:
			return {"status": "healthy"}, 200

	@property
	def logger(self) -> logging.Logger:
		if self._logger is None:
			self._logger = get_logger("Panel", parse_args().log_level.upper())
		return self._logger

	def set_start_time(self, start_time: datetime.datetime) -> None:
		self.start_time = start_time

	def run(
		self,
		host: str | None = None,
		port: int | None = None,
		debug: bool | None = None,
		use_reloader: bool = True,
		loop: asyncio.AbstractEventLoop | None = None,
		ca_certs: str | None = None,
		certfile: str | None = None,
		keyfile: str | None = None,
		**kwargs: Any,
	) -> None:
		if debug is None:
			debug = parse_args().log_level.upper() == "DEBUG"
		super().run(host=host, port=port, debug=debug, **kwargs)


def create_app(config_name: str = "default") -> Panel:
	"""Application factory."""
	return Panel(config_name)
