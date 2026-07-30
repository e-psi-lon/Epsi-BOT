import io
import sys
from typing import Literal

from epsi_bot.utils import get_logger


class MemcachedStd(io.TextIOBase):
	def __init__(self, std_type: Literal["stdout", "stderr"] = "stdout") -> None:
		self.type = std_type
		self.logger = get_logger("Memcached")
		super().__init__()

	def write(self, string: str | bytes) -> int:
		content: str
		if isinstance(string, bytes):
			content = string.decode("utf-8", errors="replace")
		else:
			content = string
		match self.type:
			case "stdout":
				self.logger.info(content)
			case "stderr":
				self.logger.error(content)
		return len(content)

	def fileno(self) -> int:
		if self.type == "stdout":
			return sys.stdout.fileno()
		else:
			return sys.stderr.fileno()

	def isatty(self) -> bool:
		if self.type == "stdout":
			return sys.stdout.isatty()
		else:
			return sys.stderr.isatty()

	def readable(self) -> bool:
		return False

	def writable(self) -> bool:
		return True

	def seekable(self) -> bool:
		return False

	def read(self, size: int | None = -1) -> str:
		raise io.UnsupportedOperation("read() not supported on MemcachedStd")
