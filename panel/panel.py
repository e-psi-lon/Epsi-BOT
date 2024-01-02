import sys
from threading import Timer
from utils import *
from flask import *
import requests
import pytube
from multiprocessing.connection import Connection, PipeConnection
import logging


class Panel(Flask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn: Connection | None = None
        # On modifie le logger pour qu'il affiche les logs selon le format qu'on a pour les autres logs
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(CustomFormatter())
        logging.basicConfig(level=logging.INFO, handlers=[console_handler])
        self.logger = logging.getLogger(__name__)

    def set_connection(self, conn: Connection):
        self.conn = conn


app = Panel(__name__)
app.secret_key = "121515145141464146EFG"
API_ENDPOINT = "https://discord.com/api/v10"
CLIENT_ID = 1167171085343666216
CLIENT_SECRET = "kH848ueQ4RGF3cKBNRJ1W1bFHI0b9bfo"
REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"

timers = {}
guilds: dict[int, list[discord.Guild]] = {}


def get_from_conn(conn: Connection, content: str, **kwargs):
    conn.send({"type": "get", "content": content, **kwargs})
    data = conn.recv()
    if isinstance(data, PipeConnection):
        data = data.get()
    return data


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
    return render_template('index.html')


@app.route('/panel')
async def panel():
    if 'token' not in session:
        return redirect(url_for('login'))
    token = session['token']
    if 'user' not in session:
        user = requests.get(f"{API_ENDPOINT}/users/@me", headers={"Authorization": f"Bearer {token['access_token']}"})
        user.raise_for_status()
        user = user.json()
        if user['avatar']:
            user['avatar_url'] = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
        if user['id'] == '708006478807695450':
            guilds[session['user_id']] = app.conn
        else:
            guilds[session['user_id']] = [guild for guild in str(get_from_conn(app.conn, "guilds")) if
                                          session["user_id"] in [str(member["id"]) for member in guild["members"]]]
        session['user'] = user
    if guilds.get(session["user_id"], None) is None:
        if session['user']['id'] == '708006478807695450':
            # On demande a la connexion avec le bot de nous donner les guilds. Pour cela on lui envoie un message et on attend la reponse
            guilds[session['user_id']] = get_from_conn(app.conn, "guilds")
        else:
            guilds[session['user_id']] = [guild for guild in get_from_conn(app.conn, "guilds") if
                                          str(session["user_id"]) in [str(member["id"]) for member in guild["members"]]]
    return render_template('panel.html', servers=guilds[session['user_id']], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
    config = await get_config(server_id, request.method != 'POST')
    if server_id not in [guild["id"] for guild in
                         guilds.get(session['user_id'], [])] or 'token' not in session or config is None:
        return redirect(url_for('panel'))
    if request.method == 'POST':
        values = request.form.to_dict()
        for key, value in values.items():
            if isinstance(getattr(config, key), bool):
                value = value == 'on'
        if config.loop_song != values['loop_song']:
            await config.set_loop_song(values['loop_song'])
        if config.loop_queue != values['loop_queue']:
            await config.set_loop_queue(values['loop_queue'])
        if config.random != values['random']:
            await config.set_random(values['random'])
        if config.position != values['position']:
            await config.set_position(values['position'])
        if config.queue != values['queue']:
            await config.edit_queue(values['queue'])
        await config.close()
        return redirect(url_for('server', server_id=server_id))
    server_data = {"loop_song": config.loop_song, "loop_queue": config.loop_queue, "random": config.random,
                   "position": config.position, "queue": config.queue, "id": server_id,
                   "name": get_from_conn(app.conn, "guild", server_id=server_id)["name"]}
    return render_template('server.html', server=server_data, app=app, pytube=pytube)


@app.route('/server/<int:server_id>/clear')
async def clear(server_id):
    config = await get_config(server_id, False)
    await config.edit_queue([])
    return redirect(url_for('server', server_id=server_id))


@app.route('/server/<int:server_id>/add', methods=['POST'])
async def add(server_id):
    config = await get_config(server_id, False)
    await config.add_song_to_queue({"title": pytube.YouTube(request.form['url']).title, "url": request.form['url'],
                                    "asker": session['user']['id']})
    await config.close()
    return redirect(url_for('server', server_id=server_id))


@app.route('/login')
async def login():
    return redirect(
        f"{API_ENDPOINT}/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={to_url(REDIRECT_URI)}&response_type=code&scope=identify%20guilds")


@app.route('/auth/discord/callback')
async def callback():
    code = request.args.get('code')
    try:
        token = await token_from_code(code)
        timer = Timer(token['expires_in'], refresh_token, [token['refresh_token']]) \
            .start()
        session['token'] = token
        user = requests.get(f"{API_ENDPOINT}/users/@me", headers={"Authorization": f"Bearer {token['access_token']}"})
        user.raise_for_status()
        user = user.json()
        session['user_id'] = user['id']
        timers[user['id']] = timer
        return redirect(url_for('panel'))
    except requests.HTTPError as e:
        return redirect(url_for('index'))


@app.route('/logout')
async def logout():
    await revoke_access_token(session['token']['access_token'])
    session.pop('token', None)
    session.pop('user', None)
    timer = timers.get(session['user_id'], None)
    if timer is not None:
        timer.cancel()
        del timers[session['user_id']]
    session.pop('user_id', None)
    return redirect(url_for('index'))


async def token_from_code(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    r = requests.post(f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
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
    r = requests.post(f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
    r.raise_for_status()
    session['token'] = r.json()
    user_id = session['user']['id']
    session["user_id"] = user_id
    timer = Timer(session['token']['expires_in'], refresh_token, [session['token']['refresh_token']]) \
        .start()
    timers[user_id] = timer
    return r.json()


async def revoke_access_token(access_token):
    data = {
        "token": access_token,
        "token_type_hint": "access_token"
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    requests.post(f"{API_ENDPOINT}/oauth2/token/revoke", data=data, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
