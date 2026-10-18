import asyncio
import datetime
import logging
import os
import signal
import sys

import discord
from dotenv import load_dotenv
from hypercorn.asyncio import serve
from hypercorn.config import Config
from tortoise import Tortoise

from epsi_bot.bot.bot import Bot
from epsi_bot.panel import create_app
from epsi_bot.utils.constants import OWNER_ID
from epsi_bot.utils.loggers import CustomFormatter, get_logger, parse_args
from epsi_bot.utils.models import get_db_url
from epsi_bot.utils.secrets import get_secret

if os.getenv("DOCKER_ENV") is not None:
	load_dotenv()

start_time = datetime.datetime.now(datetime.UTC)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(CustomFormatter("Root"))
log_level = getattr(logging, parse_args().log_level.upper(), logging.WARNING)
handler.setLevel(log_level)
logging.basicConfig(level=log_level, handlers=[handler])


async def main() -> None:
	await Tortoise.init(db_url=get_db_url(), modules={"models": ["epsi_bot.utils.models"]})
	await Tortoise.generate_schemas(safe=True)
	
	app = create_app()
	app.set_start_time(start_time)
	bot = Bot(intents=discord.Intents.all(), owner_id=OWNER_ID)
	bot.start_time = start_time
	bot.logger.info(
		f"Bot started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
		f"using python executable {sys.executable}"
	)
	app.bot = bot
	token = get_secret("TOKEN")
	if token is None:
		bot.logger.error(
			"No token found, please set the environment variable TOKEN"
		)
		sys.exit(1)
	config = Config()
	config.bind = ["0.0.0.0:8000"]
	config.errorlog = get_logger("Hypercorn")
	config.accesslog = get_logger("Hypercorn-Access")
	shutdown = asyncio.Event()
	asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, shutdown.set)
	tasks = {
        asyncio.create_task(bot.start(token), name="discord"),
        asyncio.create_task(serve(app, config, shutdown_trigger=shutdown.wait), name="web"),
        asyncio.create_task(shutdown.wait(), name="sigterm"),
    }
	try:
		done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
		for task in done:
			task.result()
	except Exception:
		bot.logger.exception("Fatal error, shutting down")
		raise
	finally:
		shutdown.set()
		await bot.close()
		try:
			await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10)
		except TimeoutError:
			bot.logger.warning("Shutdown timed out, tasks were cancelled")
		await Tortoise.close_connections()


def run() -> None:
    asyncio.run(main())

if __name__ == "__main__":
    run()