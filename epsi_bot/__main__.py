import datetime
import logging
import os
import sys
from dotenv import load_dotenv
from .panel.panel import app
import aiomultiprocess  # type: ignore
from .utils.loggers import CustomFormatter, parse_args

aiomultiprocess.set_start_method("spawn" if os.name == "nt" else "fork")
load_dotenv()

start_time = datetime.datetime.now()

def main() -> None:
	os.system("cls" if os.name == "nt" else "clear")
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