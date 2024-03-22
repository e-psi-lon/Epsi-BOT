import sys
from threading import Timer
from typing import Optional
from utils.utils import *
from quart import *
import requests
import pytube
import logging
import asyncio
import multiprocessing

class Panel(Quart):
    def __init__(self, secret_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret_key = secret_key
        self.logger.handlers.clear()
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CustomFormatter(source="Panel"))
        self.logger.addHandler(console_handler)
        self.API_ENDPOINT = "https://discord.com/api/v10"
        self.CLIENT_ID = 1167171085343666216
        self.CLIENT_SECRET = "kH848ueQ4RGF3cKBNRJ1W1bFHI0b9bfo"
        self.REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"
        self.timers = {}
        self.guilds: dict[int, list[dict]] = {}
        self.queue: Optional[multiprocessing.Queue] = None

    def set_queue(self, queue: multiprocessing.Queue):
        self.queue = queue

    async def get_from_conn(self, content: str, **kwargs):
        data = {"type": "get", "content": content, **kwargs}
        self.queue.put(data)
        print(f"Getting {data} from conn")
        return self.queue.get()


app = Panel("121515145141464146EFG", __name__)





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
        user = requests.get(f"{app.API_ENDPOINT}/users/@me",
                            headers={"Authorization": f"Bearer {token['access_token']}"})
        user.raise_for_status()
        user = user.json()
        if user['avatar']:
            user['avatar_url'] = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
        if user['id'] == '708006478807695450':
            app.guilds[session['user_id']] = app.conn
        else:
            app.guilds[session['user_id']] = [guild for guild in str(await app.get_from_conn("guilds")) if
                                              session["user_id"] in [str(member["id"]) for member in guild["members"]]]
        session['user'] = user
    if app.guilds.get(session["user_id"], None) is None:
        if session['user']['id'] == '708006478807695450':
            app.guilds[session['user_id']] = await app.get_from_conn("guilds")
        else:
            app.guilds[session['user_id']] = [guild for guild in await app.get_from_conn("guilds") if
                                              str(session["user_id"]) in [str(member["id"]) for member in
                                                                          guild["members"]]]
    return await render_template('panel.html', servers=app.guilds[session['user_id']], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
    config = await Config.get_config(server_id, request.method != 'POST')
    if server_id not in [guild["id"] for guild in
                         app.guilds.get(session['user_id'], [])] or 'token' not in session or config is None:
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
            await config.edit_queue(values['queue'])
        return redirect(url_for('server', server_id=server_id))
    server_data = {"loop_song": config.loop_song, "loop_queue": config.loop_queue, "random": config.random,
                   "position": config.position, "queue": config.queue, "id": server_id,
                   "name": await app.get_from_conn("guild", server_id=server_id)["name"]}
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
                                                await Asker.from_id(session['user']['id'])))
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
        timer = Timer(token['expires_in'], refresh_token, [token['refresh_token']]) \
            .start()
        session['token'] = token
        user = requests.get(f"{app.API_ENDPOINT}/users/@me",
                            headers={"Authorization": f"Bearer {token['access_token']}"})
        user.raise_for_status()
        user = user.json()
        session['user_id'] = user['id']
        app.timers[user['id']] = timer
        return redirect(url_for('panel'))
    except requests.HTTPError:
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
    r = requests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
                      auth=(app.CLIENT_ID, app.CLIENT_SECRET))
    r.raise_for_status()
    json_data = r.json()
    return json_data


async def refresh_token(token):
    data = {
        "grant_type": "refresh_token",
        "refresh_token": token
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    r = requests.post(f"{app.API_ENDPOINT}/oauth2/token", data=data, headers=headers,
                      auth=(app.CLIENT_ID, app.CLIENT_SECRET))
    r.raise_for_status()
    session['token'] = r.json()
    user_id = session['user']['id']
    session["user_id"] = user_id
    timer = Timer(session['token']['expires_in'],
                  lambda: asyncio.run(refresh_token(session['token']['refresh_token']))) \
        .start()
    app.timers[user_id] = timer
    return r.json()


async def revoke_access_token(access_token):
    data = {
        "token": access_token,
        "token_type_hint": "access_token"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    requests.post(f"{app.API_ENDPOINT}/oauth2/token/revoke", data=data, headers=headers,
                  auth=(app.CLIENT_ID, app.CLIENT_SECRET))
