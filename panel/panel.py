import logging
import multiprocessing
import os
from logging.config import dictConfig
from typing import Optional

import aiohttp
import pytube  # type: ignore
from dotenv import load_dotenv
from quart import Quart, session, redirect, url_for, render_template, request
from quart.logging import default_handler
from quart_session import Session  # type: ignore

from utils import (PanelToBotRequest,
                   GuildData,
                   UserData,
                   RequestType,
                   ConfigData,
                   AsyncTimer,
                   Config,
                   Song,
                   Asker,
                   AsyncRequests as Requests,
                   )

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
        logging.getLogger(__name__).removeHandler(default_handler)
        super().__init__(*args, **kwargs)
        self.secret_key = secret_key
        self.API_ENDPOINT = "https://discord.com/api/v10"
        self.CLIENT_ID = 1167171085343666216
        self.CLIENT_SECRET = os.environ['CLIENT_SECRET']
        self.REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"
        self.timers: dict[int, AsyncTimer] = {}
        self.queue: Optional[multiprocessing.Queue[PanelToBotRequest | GuildData | UserData | list[GuildData]]] = None
        self.config['SESSION_TYPE'] = 'memcached'
        Session(self)

    def set_queue(self, queue: multiprocessing.Queue):
        self.queue = queue

    async def get_from_bot(self, content: str, **kwargs) -> GuildData | UserData | list[GuildData]:
        data = PanelToBotRequest.create(RequestType.GET, content, **kwargs)
        if self.queue is None:
            raise ValueError("Queue is not set")
        self.queue.put(data)
        self.logger.info(f"Getting {data} from queue")
        response = None
        while self.queue.qsize() == 1:
            continue
        while self.queue.empty():
            continue
        response = self.queue.get()
        self.logger.info(f"Got {response} from queue")
        return response

    async def post_to_bot(self, data: dict):
        request_ = PanelToBotRequest.create(RequestType.POST, data)
        if self.queue is None:
            raise ValueError("Queue is not set")
        self.queue.put(request_)
        self.logger.info(f"Posting {request_} to conn")


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
        user = await Requests.get(f"{app.API_ENDPOINT}/users/@me",
                                  headers={"Authorization": f"Bearer {token['access_token']}"})
        user = UserData.from_api_response(user)
        session['guilds'] = await app.get_from_bot("guilds", user_id=session['user_id'])
        session['user'] = user
    if session.get('guilds', None) is None:
        session['guilds'] = await app.get_from_bot("guilds", user_id=session['user_id'])
    return await render_template('panel.html', servers=session['guilds'], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
    config = await Config.get_config(server_id, request.method != 'POST')
    if server_id not in [guild["id"] for guild in
                         session.get(session['guilds'], [])] or 'token' not in session or config is None:
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
        if config.queue_dict != values['queue']:
            await config.edit_queue(
                [await Song.create(song['title'], song['url'], await Asker.from_id(song['asker_id'])) for song in
                 values['queue']])
        return redirect(url_for('server', server_id=server_id))
    server_data = {"loop_song": config.loop_song, "loop_queue": config.loop_queue, "random": config.random,
                   "position": config.position, "queue": config.queue, "id": server_id,
                   "name": (await app.get_from_bot("guild", server_id=server_id)).name}
    server_data = ConfigData(config.loop_song, config.loop_queue, config.random, config.position, config.queue,
                             server_id, (await app.get_from_bot("guild", server_id=server_id)).name)
    return await render_template('server.html', server=server_data, app=app, pytube=pytube)


@app.route('/server/<int:server_id>/clear')
async def clear(server_id):
    config = await Config.get_config(server_id, False)
    await config.clear_queue()
    return redirect(url_for('server', server_id=server_id))


@app.route('/server/<int:server_id>/add', methods=['POST'])
async def add(server_id):
    config = await Config.get_config(server_id, False)
    await config.add_to_queue(await Song.create(pytube.YouTube((await request.form)['url']).title,
                                                (await request.form)['url'],
                                                await Asker.from_id(session['user'].id)))
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
        timer = AsyncTimer(token['expires_in'], refresh_token, [token['refresh_token']])
        timer.start()
        session['token'] = token
        user = await Requests.get(f"{app.API_ENDPOINT}/users/@me",
                                  headers={"Authorization": f"Bearer {token['access_token']}"})
        session['user_id'] = user['id']
        app.timers[user['id']] = timer
        return redirect(url_for('panel'))
    except aiohttp.ClientResponseError as e:
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


async def token_from_code(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": app.REDIRECT_URI
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    r = await Requests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
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
    r = await Requests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
                            auth=aiohttp.BasicAuth(str(app.CLIENT_ID), str(app.CLIENT_SECRET)))
    session['token'] = r
    user_id = session['user'].id
    session["user_id"] = user_id
    timer = AsyncTimer(session['token']['expires_in'], refresh_token, session['token']['refresh_token'])
    timer.start()
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
    await Requests.post(f"{app.API_ENDPOINT}/oauth2/token/revoke", data=data, headers=headers,
                        auth=aiohttp.BasicAuth(str(app.CLIENT_ID), str(app.CLIENT_SECRET)))
