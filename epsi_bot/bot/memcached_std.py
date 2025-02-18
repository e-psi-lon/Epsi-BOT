import io
import sys
from typing import Iterable, Literal

from typing_extensions import Buffer

from ..utils import get_logger


class MemcachedStd(io.TextIOBase):
	def __init__(self, std_type: Literal["stdout", "stderr"] = "stdout", *args, **kwargs):
		self.type = std_type
		self.logger = get_logger("Memcached")
		super().__init__(*args, **kwargs)

	def write(self, string: str | Buffer) -> int:
		content: str
		if isinstance(string, Buffer):
			content = str(string, "utf-8")
		else:
			content = string
		match self.type:
			case "stdout":
				self.logger.info(content)
			case "stderr":
				self.logger.error(content)
		return len(content)

	def writelines(self, lines: Iterable[str | Buffer]) -> None:
		for line in lines:
			self.write(line)

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
		return True

	def writable(self) -> bool:
		return True
