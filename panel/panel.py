from threading import Timer
from utils import *
from flask import *
import json
from discord.ext import commands
import requests
import pytube
class Panel(Flask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot: commands.Bot | None = None

    def set_bot(self, bot: commands.Bot):
        self.bot = bot


app = Panel(__name__)
app.secret_key = "121515145141464146EFG"
API_ENDPOINT = "https://discord.com/api/v10"
CLIENT_ID = 1167171085343666216
CLIENT_SECRET = "kH848ueQ4RGF3cKBNRJ1W1bFHI0b9bfo"
REDIRECT_URI = "http://86.196.98.254/auth/discord/callback"

timers = {}
guilds: dict[int, list[discord.Guild]] = {}

def to_url(url: str) -> str:
    return url.replace(' ', '%20')\
        .replace('?', '%3F')\
        .replace('=', '%3D')\
        .replace('&', '%26')\
        .replace(':', '%3A')\
        .replace('/', '%2F')\
        .replace('+', '%2B')\
        .replace(',', '%2C')\
        .replace(';', '%3B')\
        .replace('@', '%40')\
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
            guilds[session['user_id']] = app.bot.guilds
        else:
            guilds[session['user_id']] = [guild for guild in str(app.bot.guilds) if session["user_id"] in [str(member.id) for member in guild.members]]
        session['user'] = user
    if guilds.get(session["user_id"], None) is None:
        if session['user']['id'] == '708006478807695450':
            guilds[session['user_id']] = app.bot.guilds
        else:
            guilds[session['user_id']] = [guild for guild in app.bot.guilds if str(session["user_id"]) in [str(member.id) for member in guild.members]]
    return render_template('panel.html', servers=guilds[session['user_id']], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
    server_filename = os.path.join('queue', f'{server_id}.json')
    if server_id not in [guild.id for guild in guilds.get(session['user_id'], [])] or 'token' not in session or not os.path.exists(server_filename):
        return redirect(url_for('panel'))

    if request.method == 'POST':
        with open(server_filename, 'r') as file:
            data = json.load(file)
        with open(server_filename, 'w') as file:
            values = request.form.to_dict()
            for key in values.keys():
                if values[key] != data[key]:
                    if isinstance(data[key], bool):
                        data[key] = values[key] == "on"
            json.dump(data, file, indent=4)
        return redirect(url_for('server', server_id=server_id))

    with open(server_filename, 'r') as file:
        server_data = json.load(file)
    server_data["id"] = server_id
    server_data["name"] = app.bot.get_guild(server_id).name
    return render_template('server.html', server=server_data, app=app, pytube=pytube)


@app.route('/server/<int:server_id>/clear')
async def clear(server_id): 
    server_filename = os.path.join('queue', f'{server_id}.json')
    with open(server_filename, 'r') as file:
        data = json.load(file)
    data['queue'] = []
    with open(server_filename, 'w') as file:
        json.dump(data, file, indent=4)
    return redirect(url_for('server', server_id=server_id))

@app.route('/server/<int:server_id>/add', methods=['POST'])
async def add(server_id):
    server_filename = os.path.join('queue', f'{server_id}.json')
    with open(server_filename, 'r') as file:
        data = json.load(file)
    data['queue'].append(request.form['url'])
    with open(server_filename, 'w') as file:
        json.dump(data, file, indent=4)
    return redirect(url_for('server', server_id=server_id))

@app.route('/login')
async def login():
    return redirect(f"{API_ENDPOINT}/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={to_url(REDIRECT_URI)}&response_type=code&scope=identify%20guilds")

@app.route('/auth/discord/callback')
async def callback():
    code = request.args.get('code')
    try:
        token = await token_from_code(code)
        timer = Timer(token['expires_in'], refresh_token, [token['refresh_token']])\
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
    timer = Timer(session['token']['expires_in'], refresh_token, [session['token']['refresh_token']])\
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
