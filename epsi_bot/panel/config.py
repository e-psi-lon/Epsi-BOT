from typing import Any

from quart import Quart

from epsi_bot.utils.secrets import get_secret


class Config:
	"""Base configuration."""

	SECRET_KEY = get_secret("PANEL_SECRET_KEY")
	API_ENDPOINT = "https://discord.com/api/v10"
	CLIENT_ID = 1167171085343666216
	CLIENT_SECRET = get_secret("CLIENT_SECRET")
	REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"
	SESSION_TYPE = "redis"
	DEBUG: bool

	@staticmethod
	def init_app(app: Quart) -> None:
		"""Initialize app with this config."""


class DevelopmentConfig(Config):
	"""Development configuration."""

	DEBUG = True


class ProductionConfig(Config):
	"""Production configuration."""

	DEBUG = False


config: dict[str, Any] = {
	"development": DevelopmentConfig,
	"production": ProductionConfig,
	"default": DevelopmentConfig,
}
