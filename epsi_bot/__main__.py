import datetime
import logging
import os
import sys

import aiomultiprocess  # type: ignore[import-untyped]
from dotenv import load_dotenv

from epsi_bot.panel import create_app
from epsi_bot.utils.loggers import CustomFormatter, parse_args

aiomultiprocess.set_start_method("fork")
if os.environ.get("DOCKER_ENV", False):
	load_dotenv(".env.docker")
else:
	load_dotenv()

start_time = datetime.datetime.now()


def main() -> None:
	os.system("clear")
	app = create_app()
	app.set_start_time(start_time)
	# Default logger
	handler = logging.StreamHandler(sys.stdout)
	handler.setFormatter(CustomFormatter("Root"))
	log_level = getattr(logging, parse_args().log_level.upper(), logging.INFO)
	handler.setLevel(log_level)
	logging.basicConfig(level=log_level, handlers=[handler])
	app.run(host="0.0.0.0", port=8080, use_reloader=False)


if __name__ == "__main__":
	main()
