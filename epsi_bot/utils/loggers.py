import argparse
import atexit
import copy
import functools
import logging
import logging.handlers
import os
import queue
import re
import sys
import time
from typing import ClassVar, Final

_NIX_STORE_RE = re.compile(r"^/nix/store/[a-z0-9]+-[^/]+/")
LogLevel = int | str


@functools.cache
def _module_path(pathname: str) -> str:
	if m := _NIX_STORE_RE.match(pathname):
		path = pathname[m.end():]
		path = re.sub(r"^lib/python\d+\.\d+/site-packages/", "libs.", path)
		path = re.sub(r"^lib/python\d+\.\d+/", "stdlib.", path)
		path = path.replace(os.sep, ".")
	else:
		roots = (os.path.abspath(r) for r in sys.path if r)
		best_root = max(
			(r for r in roots if pathname.startswith(r + os.sep)),
			key=len,
			default=None,
		)
		if best_root:
			path = os.path.relpath(pathname, best_root).replace(os.sep, ".")
			if os.path.basename(best_root) == "site-packages":
				path = f"libs.{path}"
		else:
			path = os.path.relpath(pathname, os.getcwd()).replace(os.sep, ".")
	return path.removesuffix(".py").lower()


class CustomFormatter(logging.Formatter):
	COLORS: ClassVar[dict[int, str]] = {
		logging.DEBUG: "\033[34m",     # Blue
		logging.INFO: "\033[32m",      # Green
		logging.WARNING: "\033[33m",   # Yellow
		logging.ERROR: "\033[31m",     # Red
		logging.CRITICAL: "\033[41m",  # Red background
	}
	def __init__(self, source: str | None = None) -> None:
		super().__init__(
			fmt=(
				"[{asctime}] {source} — {color}{levelname}\033[0m : "
				"{message} ({module_path}:{lineno})"
			),
			datefmt="%d/%m/%Y %H:%M:%S UTC",
			style="{",
		)
		self.converter = time.gmtime
		self.source = source


	def format(self, record: logging.LogRecord) -> str:
		record = copy.copy(record)
		record.__dict__.update(
			source=self.source or record.__dict__.get("source", record.name),
			color=self.COLORS.get(record.levelno, ""),
			module_path=_module_path(record.pathname),
		)
		return super().format(record)


class _SourceFilter(logging.Filter):
	def __init__(self, source: str) -> None:
		super().__init__()
		self.source = source

	def filter(self, record: logging.LogRecord) -> bool:
		record.source = self.source
		return True


_VALID_LEVELS: Final[set[str]] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument(
		"--log-level",
		default="INFO",
		help=f"Log level (valid: {', '.join(_VALID_LEVELS)})",
	)
	parsed = parser.parse_known_args()[0]
	if parsed.log_level.upper() not in _VALID_LEVELS:
		parsed.log_level = "INFO"
	return parsed


_log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
_listener: logging.handlers.QueueListener | None = None
_configured_loggers: set[str] = set()

@functools.cache
def _default_level() -> str:
	return parse_args().log_level.upper()


def _ensure_listener() -> None:
	global _listener
	if _listener is not None:
		return
	stream_handler = logging.StreamHandler()
	stream_handler.setFormatter(CustomFormatter())  # source comes from the record
	_listener = logging.handlers.QueueListener(
		_log_queue, stream_handler, respect_handler_level=True
	)
	_listener.start()
	atexit.register(_listener.stop)


def get_logger(name: str, level: LogLevel | None = None) -> logging.Logger:
	"""Get a logger with the specified name and level."""
	logger = logging.getLogger(name)
	if name in _configured_loggers:
		return logger

	_ensure_listener()
	handler = logging.handlers.QueueHandler(_log_queue)
	handler.addFilter(_SourceFilter(name))

	logger.propagate = False
	logger.handlers.clear()
	logger.addHandler(handler)
	logger.setLevel(level if level is not None else _default_level())
	_configured_loggers.add(name)
	return logger