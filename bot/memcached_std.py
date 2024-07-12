import io
import sys

from utils import get_logger

class MemcachedStd(io.TextIOBase):
    def __init__(self, type: str = "stdout", *args, **kwargs):
        self.type = type
        self.logger = get_logger("Memcached")
        super().__init__(*args, **kwargs)

    def write(self, string: str) -> int:
        match self.type:
            case "stdout":
                self.logger.info(string)
            case "stderr":
                self.logger.error(string)
        return len(string)

    def writelines(self, lines: list[str]) -> None:
        for line in lines:
            self.write(line)

    def fileno(self) -> int:
        return sys.stdout.fileno()
    
    def isatty(self) -> bool:
        return sys.stdout.isatty()
    
    def readable(self) -> bool:
        return True
    
    def writable(self) -> bool:
        return True
