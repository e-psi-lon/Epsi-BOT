import asyncio
import datetime
import logging
import os
from asyncio import TimerHandle
from typing import Any, Optional

import aiohttp
import aiomcache
import discord
import psutil
import tortoise.fields.relational as relational
from aiocache import MemcachedCache
from aiocache.serializers import PickleSerializer
from aiomultiprocess import Process  # type: ignore[import-untyped]
from dotenv import load_dotenv
from quart import Quart, session, redirect, url_for, render_template, request, websocket
from quart_session import Session  # type: ignore[import-untyped]
from tortoise import Tortoise, fields
from tortoise.contrib.quart import register_tortoise
from werkzeug.utils import cached_property
from werkzeug.wrappers.response import Response

from epsi_bot.bot.bot import start, Bot
from epsi_bot.utils import (UserData,
                            ConfigData,
                            AsyncRequests,
                            get_logger,
                            parse_args,
                            models,
                            YOUTUBE_REGEX,
                            IPCManager,
                            get_youtube,
                            )
from epsi_bot.utils.models import BaseModel

load_dotenv()


class Panel(Quart):
	def __init__(self, secret_key: str, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot_process = None
		self.start_time = None
		self.bot_process: Process
		self.secret_key = secret_key
		self.API_ENDPOINT = "https://discord.com/api/v10"
		self.CLIENT_ID = 1167171085343666216
		self.CLIENT_SECRET = os.environ['CLIENT_SECRET']
		self.REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"
		self.timers: dict[int, TimerHandle] = {}
		self.ipc, self.bot_ipc = IPCManager.create_pair()
		self.config['SESSION_TYPE'] = 'memcached'
		self.start_time: datetime.datetime
		self.handle = self.ipc.handle
		self.get_from_bot = self.ipc.request
		self.post_to_bot = self.ipc.send
		Session(self)
		register_tortoise(
			self,
			db_url='sqlite://database/database.db',
			modules={'models': ['epsi_bot.utils.models']}
		)

	@cached_property
	def logger(self) -> logging.Logger:
		return get_logger("Panel")

	def set_start_time(self, start_time: datetime.datetime) -> None:
		self.start_time = start_time

	async def start_bot(self):
		bot = Bot(self.bot_ipc, intents=discord.Intents.all())
		await start(bot, self.start_time)

	async def startup(self):
		if not os.path.exists("database/database.db"):
			if not os.path.exists("database/"):
				os.mkdir("database/")
			with open("database/database.db", "w") as f:
				f.write("")
			await Tortoise.init(
				db_url='sqlite://database/database.db',
				modules={'models': ['epsi_bot.utils.models']}
			)
			await Tortoise.generate_schemas(safe=True)
		self.bot_process = Process(target=self.start_bot, name="Bot")
		await self.ipc.start()
		self.bot_process.start()
		return await super().startup()

	def run(
			self,
			host: str | None = None,
			port: int | None = None,
			debug: bool | None = parse_args().log_level.upper() == "DEBUG",
			use_reloader: bool = True,
			loop: asyncio.AbstractEventLoop | None = None,
			ca_certs: str | None = None,
			certfile: str | None = None,
			keyfile: str | None = None,
			**kwargs: Any,
	) -> None:
		super().run(host=host, port=port, use_reloader=use_reloader, loop=loop, ca_certs=ca_certs, certfile=certfile,
		            debug=debug,
		            keyfile=keyfile, **kwargs)

	@staticmethod
	async def get_from_bot(channel: str, **payload) -> Any:
		async with MemcachedCache(serializer=PickleSerializer(), namespace="ipc_cache") as cache:
			if await cache.exists(f"{channel}_{payload}"):
				return await cache.get(f"{channel}_{payload}")
			else:
				response = await app.bot_ipc.request(channel, **payload)
				await cache.set(f"{channel}_{payload}", response, ttl=60)
				return response


app = Panel(os.environ['PANEL_SECRET_KEY'], __name__)


@app.ipc.handle("stop")
async def shutdown():
	await app.bot_process.join()
	await Tortoise.close_connections()
	await app.shutdown()
	exit(0)


def to_url(url: str) -> str:
	return url.replace(' ', '%20') \
		.replace('?', '%3F') \
		.replace('=', '%3D') \
		.replace('&', '%26') \
		.replace(':', '%3A') \
		.replace('/', '%2F') \
		.replace('+', '%2B') \
		.replace(',', '%2C') \
		.replace(';', '%3B') \
		.replace('@', '%40') \
		.replace('#', '%23')


@app.route('/')
async def index():
	if 'token' in session:
		return redirect(url_for('panel'))
	return await render_template('index.html')


@app.route('/panel')
async def panel():
	if 'token' not in session:
		return redirect(url_for('login'))
	token = session['token']
	if 'user' not in session:
		user = await AsyncRequests.get(f"{app.API_ENDPOINT}/users/@me",
		                               headers={"Authorization": f"Bearer {token['access_token']}"})
		user = UserData.from_api_response(user)
		session['guilds'] = await app.ipc.request("guilds", user_id=session['user_id'])
		session['user'] = user
	if session.get('guilds', None) is None:
		session['guilds'] = await app.ipc.request("guilds", user_id=session['user_id'])
	app.logger.debug(f"Showing panel with user:\n- {session['user']}\nwho has guilds:\n- {session['guilds']}")
	return await render_template('panel.html', servers=session['guilds'], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id: int) -> None | str | Response:
	config = await models.Server.get_or_none(server_id=server_id)
	if server_id not in [guild["id"] for guild in
	                     session.get('guilds', [])] or 'token' not in session or config is None:
		return redirect(url_for('panel'))
	if request.method == 'POST':
		values = (await request.form).to_dict()
		for key, value in values.items():
			if isinstance(getattr(config, key), bool):
				values[key] = value == "on"
		if config.loop_song != values['loop_song']:
			config.loop_song = values['loop_song']
		if config.loop_queue != values['loop_queue']:
			config.loop_queue = values['loop_queue']
		if config.random != values['random']:
			config.random = values['random']
		if config.position != values['position']:
			config.position = values['position']
		if config.queue != values['queue']:
			await config.queue.all().delete()
			await models.Song.bulk_create(
				[models.Song(name=song['title'], url=song['url']) for song in values['queue']], ignore_conflicts=True)
			await models.Asker.bulk_create([models.Asker(discord_id=song['asker_id']) for song in values['queue']],
			                               ignore_conflicts=True)
			await models.Queue.bulk_create([models.Queue(server=config, song=await models.Song.get(name=song['title']),
			                                             asker=await models.Asker.get(discord_id=song['asker_id'])) for
			                                song in values['queue']], ignore_conflicts=True)
			await config.save()
			return redirect(url_for('server', server_id=server_id))
		server_data = ConfigData(config.loop_song, config.loop_queue, config.random, config.position,
		                         await config.queue,
		                         # type: ignore[arg-type]
		                         server_id, (await app.get_from_bot("guild", server_id=server_id)).name,
		                         config.volume)  # type: ignore[arg-type, attr-defined]
		return await render_template('server.html', server=server_data, app=app, get_youtube=get_youtube,
		                             yt_regex=YOUTUBE_REGEX)


@app.route('/server/<int:server_id>/clear')
async def clear(server_id: int) -> Response:
	config = await models.Server.get(server_id=server_id)
	await config.queue.all().delete()
	return redirect(url_for('server', server_id=server_id))


@app.route('/server/<int:server_id>/add', methods=['POST'])
async def add(server_id: int) -> Response:
	config = await models.Server.get(server_id=server_id)
	song, _ = await models.Song.get_or_create(name=(await request.form)['name'], url=(await request.form)['url'])
	asker, _ = await models.Asker.get_or_create(discord_id=session['user'].id)
	await (await models.Queue.create(server=config, song=song, asker=asker)).save()
	return redirect(url_for('server', server_id=server_id))


@app.route('/login')
async def login():
	return redirect(
		f"{app.API_ENDPOINT}/oauth2/authorize?client_id={app.CLIENT_ID}&redirect_uri={to_url(app.REDIRECT_URI)}"
		f"&response_type=code&scope=identify%20guilds")


@app.route('/auth/discord/callback')
async def callback():
	code = request.args.get('code')
	try:
		token = await token_from_code(code)
		timer = asyncio.get_event_loop().call_later(token['expires_in'], asyncio.get_event_loop().create_task,
		                                            refresh_token(token['refresh_token']))
		session['token'] = token
		user = await AsyncRequests.get(f"{app.API_ENDPOINT}/users/@me",
		                               headers={"Authorization": f"Bearer {token['access_token']}"})
		session['user_id'] = user['id']
		app.timers[user['id']] = timer
		return redirect(url_for('panel'))
	except aiohttp.ClientResponseError:
		return redirect(url_for('index'))


@app.route('/logout')
async def logout():
	await revoke_access_token(session['token']['access_token'])
	session.pop('token', None)
	session.pop('user', None)
	timer = app.timers.get(session['user_id'], None)
	if timer is not None:
		timer.cancel()
		del app.timers[session['user_id']]
	session.pop('user_id', None)
	return redirect(url_for('index'))


@app.route('/admin')
async def admin():
	app.logger.info(f"Admin page requested by {request.remote_addr}")
	if not request.remote_addr.startswith("192.168.83.") and request.remote_addr != "127.0.0.1":
		return 403
	return await render_template('admin.html')


@app.websocket('/admin')
async def admin_ws():
	app.logger.info(f"Admin websocket requested by {websocket.remote_addr}")
	if not websocket.remote_addr.startswith("192.168.83.") and websocket.remote_addr != "127.0.0.1":
		return 403
	try:
		while True:
			message = await websocket.receive()
			if message == "refresh":
				# Get cache stats
				cache_stats = {key.decode(): value.decode() for key, value in (await get_cache_stats()).items()}

				# Get process information
				current_process = psutil.Process(os.getpid())
				bot_process = psutil.Process(app.bot_process.pid)

				process_info = {
					"main": {
						"pid": current_process.pid,
						"cpu_percent": current_process.cpu_percent(interval=0.1),
						"memory_percent": current_process.memory_percent(),
						"memory_usage": current_process.memory_info().rss,
						"threads": len(current_process.threads()),
						"uptime": (datetime.datetime.now() - app.start_time).total_seconds()
					},
					"bot": {
						"pid": bot_process.pid,
						"cpu_percent": bot_process.cpu_percent(interval=0.1),
						"memory_percent": current_process.memory_percent(),
						"memory_usage": bot_process.memory_info().rss,
						"voice_channels": await app.get_from_bot("voice_channels"),
						"connected_servers": await app.get_from_bot("connected_servers")
					}
				}

				# Get database information
				tables: list[type[BaseModel]] = [
					getattr(models, model_name)
					for model_name in models.__all__
					if isinstance(getattr(models, model_name), type)
					   and issubclass(getattr(models, model_name), models.BaseModel)
					   and getattr(models, model_name) != models.BaseModel
				]
				# noinspection PyProtectedMember
				columns = {table: table._meta.fields_map for table in tables}
				formatted_columns = format_table_info(columns)
				database: dict[str, dict[str, tuple[bool | None, list[str]]]] = {}
				for table, formatted_cols in formatted_columns.items():
					# Fetch all rows for the table in a single query
					all_rows = await table.all()
					table_data = {}

					for col_name, col_type in formatted_cols.items():
						# Extract values for each column from the already fetched rows
						values = []
						for row in all_rows:
							value = getattr(row, col_name)
							if col_type is True:  # Primary key
								values.append(str(value))
							elif col_type is None:  # Foreign key
								values.append(str((await value).pk))
							else:  # Regular field
								values.append(str(value))
						table_data[col_name] = (col_type, values)

					# We filter the table data
					# If there's fk_name and fk_name_id, we remove fk_name_id
					table_data = {k: v for k, v in table_data.items() if
					              not (k.endswith("_id") and k[:-3] in table_data.keys())}

					database[table.__name__] = table_data
				await websocket.send_json({
					"cache_stats": cache_stats,
					"process_info": process_info,
					"database": database
				})
	except Exception as e:
		app.logger.exception(e)
		await websocket.close(code=1001)


def register_error_handlers():
	for code in range(400, 500):
		try:
			@app.errorhandler(code)
			async def _error_page(e):
				# Si c'est une resource (fichier) qui n'est pas trouvée
				if e.name == "NotFound":
					return 404
				return await render_template('error.html', code=code), code
		except ValueError:
			continue


register_error_handlers()


async def token_from_code(code):
	data = {
		"grant_type": "authorization_code",
		"code": code,
		"redirect_uri": app.REDIRECT_URI
	}
	headers = {
		"Content-Type": "application/x-www-form-urlencoded"
	}
	r = await AsyncRequests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
	                             auth=aiohttp.BasicAuth(str(app.CLIENT_ID), str(app.CLIENT_SECRET)))
	return r


async def refresh_token(token):
	data = {
		"grant_type": "refresh_token",
		"refresh_token": token
	}
	headers = {
		"Content-Type": "application/x-www-form-urlencoded"
	}
	r = await AsyncRequests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
	                             auth=aiohttp.BasicAuth(str(app.CLIENT_ID), str(app.CLIENT_SECRET)))
	session['token'] = r
	user_id = session['user'].id
	session["user_id"] = user_id
	timer = asyncio.get_event_loop().call_later(session['token']['expires_in'], asyncio.get_event_loop().create_task,
	                                            refresh_token(session['token']['refresh_token']))
	app.timers[user_id] = timer
	return r


async def revoke_access_token(access_token):
	data = {
		"token": access_token,
		"token_type_hint": "access_token"
	}
	headers = {
		"Content-Type": "application/x-www-form-urlencoded"
	}
	await AsyncRequests.post(f"{app.API_ENDPOINT}/oauth2/token/revoke", data=data, headers=headers,
	                         auth=aiohttp.BasicAuth(str(app.CLIENT_ID), str(app.CLIENT_SECRET)))


def format_table_info(
		tables_metadata: dict[type[BaseModel], dict[str, fields.Field]]
) -> dict[type[BaseModel], dict[str, bool | None]]:
	formatted = {}
	for table, columns in tables_metadata.items():
		formatted[table] = {
			name: True if col.pk
			else None if isinstance(col, relational.ForeignKeyFieldInstance)
			else False
			for name, col in columns.items() if not isinstance(col, relational.BackwardFKRelation)
		}
	return formatted


async def get_cache_stats() -> Optional[dict[bytes, bytes]]:
	"""Function to get the cache statistics.

	Returns
	-------
	dict
		The cache statistics.
	"""
	mc = aiomcache.Client("127.0.0.1", 11211)
	stats = await mc.stats()
	await mc.close()
	return stats
