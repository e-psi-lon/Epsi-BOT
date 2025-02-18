import argparse
import logging
import os
from typing import Optional, Any


class CustomFormatter(logging.Formatter):
	"""Custom formatter for the bot and the panel's logs"""

	def __init__(self, source: str, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self.source = source

	FORMAT = "[{asctime}] {source} {levelname} : {message} ({path}:{lineno})\033[0m"

	FORMATS = {
		logging.DEBUG: "\033[34m" + FORMAT,  # Blue
		logging.INFO: "\033[32m" + FORMAT,  # Green
		logging.WARNING: "\033[33m" + FORMAT,  # Yellow
		logging.ERROR: "\033[31m" + FORMAT,  # Red
		logging.CRITICAL: "\033[41m" + FORMAT  # Red
	}

	def format(self, record: logging.LogRecord) -> str:
		log_fmt = self.FORMATS.get(record.levelno)
		path = os.path.relpath(record.pathname, os.getcwd()).replace(os.sep, ".").lower()
		if path.endswith(".py"):
			path = path[:-3]
		path = path.replace(".venv.lib.site-packages.", "libs.")
		formatter = logging.Formatter(log_fmt, "%d/%m/%Y %H:%M:%S", "{", True,
		                              defaults={"source": self.source, "path": path})
		return formatter.format(record)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	parser.add_argument("--log-level", type=str, default="INFO",
	                    help="The log level of the bot (valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL)",
	                    required=False)
	parsed = parser.parse_known_args()[0]
	if not hasattr(parsed, "log_level") or parsed.log_level.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR",
	                                                                        "CRITICAL"]:
		setattr(parsed, "log_level", "INFO")
	return parsed


configured_loggers = set()


def get_logger(name: str, level: Optional[int] = parse_args().log_level.upper()) -> logging.Logger:
	"""Get a logger with the specified name and level"""
	logger = logging.getLogger(name)
	if name in configured_loggers:
		return logger
	logger.propagate = False
	if level is not None:
		logger.setLevel(level)
	else:
		logger.setLevel(logging.INFO)
	for handler in logger.handlers:
		if isinstance(handler.formatter, CustomFormatter):
			break
	else:
		logger.handlers.clear()
	handler = logging.StreamHandler()
	handler.setFormatter(CustomFormatter(name))
	logger.addHandler(handler)
	configured_loggers.add(name)
	return logger
