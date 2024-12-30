import asyncio
import datetime
import json
import logging
import os
from asyncio import TimerHandle
from logging.config import dictConfig
import re
from typing import NoReturn, Optional, Any

import aiocache.serializers
import aiohttp
import discord
import multiprocessing

import peewee
import pytubefix  # type: ignore
from aiocache import MemcachedCache
from dotenv import load_dotenv
from quart import Quart, session, redirect, url_for, render_template, request, websocket
from quart_session import Session  # type: ignore

from utils import (PanelBotRequest,
                   PanelBotResponse,
                   UserData,
                   RequestType,
                   ConfigData,
                   AsyncRequests,
                   get_logger,
                   Event,
                   set_callback,
                   )
from utils.loggers import parse_args
import utils.models as models
from aiomultiprocess import Process
from bot.bot import start, Bot
from utils.models import BaseModel
from utils.panel_ import get_cache_stats

load_dotenv()

dictConfig({
	'version': 1,
	'formatters': {'default': {
		'()': 'utils.CustomFormatter',
		'source': 'Panel'
	}},
	'handlers': {'console': {
		'class': 'logging.StreamHandler',
		'formatter': 'default',
		'stream': 'ext://sys.stdout',
	}},
	'root': {
		'level': logging.getLogger('__main__').getEffectiveLevel(),
		'handlers': ['console']
	}
})

class Panel(Quart):
	def __init__(self, secret_key: str, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot_process: Optional[Process] = None
		self.secret_key = secret_key
		self.API_ENDPOINT = "https://discord.com/api/v10"
		self.CLIENT_ID = 1167171085343666216
		self.CLIENT_SECRET = os.environ['CLIENT_SECRET']
		self.REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"
		self.timers: dict[int, TimerHandle] = {}
		self.queue: Optional[multiprocessing.Queue[PanelBotRequest | PanelBotResponse]] = multiprocessing.Queue()
		self.config['SESSION_TYPE'] = 'memcached'
		self.start_time: Optional[datetime.datetime] = None
		self.bot_event = Event()
		self.event = Event()
		Session(self)

	@property
	def logger(self) -> logging.Logger:
		return get_logger("Panel")

	def set_start_time(self, start_time: datetime.datetime):
		self.start_time = start_time

	async def start_bot(self, queue: multiprocessing.Queue, start_time: datetime.datetime) -> NoReturn:
		if not os.path.exists("database/database.db"):
			if not os.path.exists("database/"):
				os.mkdir("database/")
			with open("database/database.db", "w") as f:
				f.write("")
			db = models.database
			db.create_tables([models.Asker, models.Playlist, models.PlaylistSong, models.Queue, models.Server, models.ServerPlaylist, models.Song, models.UserPlaylist], safe=True)
		await set_callback(self.event, self.read_queue, asyncio.get_event_loop())
		bot: Bot = Bot(queue, self.event, self.bot_event, intents=discord.Intents.all())
		await start(bot, start_time)

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
		self.bot_process: Process = Process(target=self.start_bot, args=(self.queue, self.start_time))
		self.bot_process.start()
		super().run(host=host, port=port, use_reloader=use_reloader, loop=loop, ca_certs=ca_certs, certfile=certfile, debug=debug,
					keyfile=keyfile, **kwargs)


	async def get_from_bot(self, content: str, **kwargs) -> PanelBotResponse:
		data = PanelBotRequest.create(RequestType.GET, content, **kwargs)
		if self.queue is None:
			raise ValueError("Queue is not set")
		# Avoid bot call if data already cached
		async with MemcachedCache(serializer=aiocache.serializers.PickleSerializer()) as cache:
			if await cache.exists(f"{content}:{kwargs}", namespace="panel"):
				return await cache.get(f"{content}:{kwargs}", namespace="panel")
		self.queue.put(data)
		await self.bot_event.set()
		self.logger.info(f"Getting {data} from bot")
		await self.event.wait()
		response: PanelBotResponse = self.queue.get()
		await self.event.clear()
		self.logger.info(f"Got {response} from bot")
		async with MemcachedCache(serializer=aiocache.serializers.PickleSerializer()) as cache:
			await cache.set(f"{content}:{kwargs}", response, namespace="panel")
		return response

	async def post_to_bot(self, data: dict):
		request_ = PanelBotRequest.create(RequestType.POST, json.dumps(data))
		if self.queue is None:
			raise ValueError("Queue is not set")
		self.queue.put(request_)
		await self.bot_event.set()
		self.logger.info(f"Posting {request_} to bot")

	async def read_queue(self) -> Optional[NoReturn]:
		message = self.queue.get()
		self.logger.info(f"Got {message} from connection")
		if not isinstance(message, PanelBotRequest):
			raise TypeError("")
		match message.type:
			case RequestType.GET:
				return self.queue.put(message)
			case RequestType.POST:
				if message.content == "stop":
					await self.shutdown()
					exit(0)
				return self.queue.put(message)


app = Panel(os.environ['PANEL_SECRET_KEY'], __name__)


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
		session['guilds'] = (await app.get_from_bot("guilds", user_id=session['user_id'])).content
		session['user'] = user
	if session.get('guilds', None) is None:
		session['guilds'] = (await app.get_from_bot("guilds", user_id=session['user_id'])).content
	app.logger.debug(f"Showing panel with user:\n- {session['user']}\nwho has guilds:\n- {session['guilds']}")
	return await render_template('panel.html', servers=session['guilds'], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
	config: models.Server = models.Server.get_or_none(server_id=server_id)
	if server_id not in [guild["id"] for guild in session.get('guilds', [])] or 'token' not in session or config is None:
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
			new_queue = [{"name": song['title'], "url": song['url'], "asker": song['asker_id']} for song in values['queue']]
			config.queue = new_queue
		config.save()
		return redirect(url_for('server', server_id=server_id))
	server_data = ConfigData(config.loop_song, config.loop_queue, config.random, config.position, config.queue,
							 server_id, (await app.get_from_bot("guild", server_id=server_id)).content.name, config.volume)
	yt_regex = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/((watch\?v=)|(embed/)|(v/)|(.+\?v=))?([^&=%\?]{11})')
	return await render_template('server.html', server=server_data, app=app, pytubefix=pytubefix, yt_regex=yt_regex)


@app.route('/server/<int:server_id>/clear')
async def clear(server_id):
	config: models.Server = models.Server.get(server_id=server_id)
	for song in config.queue:
		song.delete().execute()
	return redirect(url_for('server', server_id=server_id))


@app.route('/server/<int:server_id>/add', methods=['POST'])
async def add(server_id):
	config = models.Server.get(server_id=server_id)
	song: models.Song = models.Song.get_or_create(name=(await request.form)['name'], url=(await request.form)['url'])
	asker: models.Asker = models.Asker.get_or_create(discord_id=session['user'].id)
	models.Queue.create(server=config, song=song, asker=asker).save()
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
		timer = asyncio.get_event_loop().call_later(token['expires_in'], asyncio.get_event_loop().create_task, refresh_token(token['refresh_token']))
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
	if not request.remote_addr.startswith("192.168.83."):
		return 403
	return await render_template('admin.html')


@app.websocket('/admin')
async def admin_ws():
	app.logger.info(f"Admin websocket requested by {websocket.remote_addr}")
	if not websocket.remote_addr.startswith("192.168.83."):
		return 403
	try:
		while True:
			message = await websocket.receive()
			if message == "refresh":
				stats = {key.decode(): value.decode() for key, value in (await get_cache_stats()).items()}
				tables = [table for table in models.database.get_tables() if table not in ("sqlite_sequence", "sqlite_master")]
				columns_metadata = {table: models.database.get_columns(table) for table in tables}
				columns_foreign = {table: models.database.get_foreign_keys(table) for table in tables}
				# Pour chaque columns_metadata, si il existe une columns_foreign de la meme table et du meme nom, on remplace la colomn_metadata par la columns_foreign
				columns = {table: [col for col in columns_metadata[table] if col.name not in [foreign.column for foreign in columns_foreign[table]]] + columns_foreign[table]
				           						   for table in tables}
				columns = format_table_info(columns)
				values = {
					table._meta.table_name: [
						{col: (getattr(row, col).id if isinstance(getattr(row, col), models.BaseModel) else getattr(row, col))
						 for col in columns[table._meta.table_name]}
						for row in table.select(*[getattr(table, col) for col in columns[table._meta.table_name]])
					]
					for table in (models.Asker, models.Playlist, models.PlaylistSong, models.Queue, models.Server, models.ServerPlaylist, models.Song, models.UserPlaylist, models.SongListenCount)
				}
				for table_data in values.values():
					for row in table_data:
						for key, value in row.items():
							if isinstance(value, datetime.datetime):
								row[key] = value.isoformat()
							elif isinstance(value, bytes):
								row[key] = value.decode()
				await websocket.send_json({"stats": stats, "tables": tables, "columns": columns, "values": values})
	except Exception as e:
		app.logger.error(f"WebSocket error: {e}")
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

def format_table_info(tables_metadata: dict[BaseModel, list[peewee.ColumnMetadata | peewee.ForeignKeyMetadata]]) -> dict[BaseModel, dict[str, bool | None]]:
	formatted = {}
	for table_name, columns in tables_metadata.items():
		formatted[table_name] = {
			col.name if isinstance(col, peewee.ColumnMetadata) else col.column:
				col.primary_key if isinstance(col, peewee.ColumnMetadata) else None
			for col in columns
		}
	return formatted
