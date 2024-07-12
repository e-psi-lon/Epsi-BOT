import argparse
import logging
import os
from typing import Optional


class CustomFormatter(logging.Formatter):
    """Custom formatter for the bot and the panel's logs"""

    def __init__(self, source: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source

    format_ = "[{asctime}] {source} {levelname} : {message} ({path}:{lineno})\033[0m"

    FORMATS = {
        logging.DEBUG: "\033[34m" + format_,  # Blue
        logging.INFO: "\033[32m" + format_,  # Green
        logging.WARNING: "\033[33m" + format_,  # Yellow
        logging.ERROR: "\033[31m" + format_,  # Red
        logging.CRITICAL: "\033[41m" + format_  # Red
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        path = record.pathname.lower().replace(os.getcwd().lower() + "\\", "").replace("\\", "/").replace("/",
                                                                                                          ".")[:-3]
        path = path.replace(".venv.lib.site-packages.", "libs.")
        formatter = logging.Formatter(log_fmt, "%d/%m/%Y %H:%M:%S", "{", True,
                                      defaults={"source": self.source, "path": path})
        return formatter.format(record)



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", type=str, default="INFO", help="The log level of the bot", required=False)
    return parser.parse_known_args()[0]

configured_loggers = set()

def get_logger(name: str, level: Optional[int] = parse_args().log_level) -> logging.Logger:
    """Get a logger with the specified name and level"""
    logger = logging.getLogger(name)
    if name in configured_loggers:
        return logger
    logger.propagate = False
    if level is not None:
        logger.setLevel(level)
    else:
        logger.setLevel(logging.INFO)
    if logger.hasHandlers() and not isinstance(logger.handlers[0].formatter, CustomFormatter):
        for handler in logger.handlers:
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter(name))
    logger.addHandler(handler)
    configured_loggers.add(name)
    return logger