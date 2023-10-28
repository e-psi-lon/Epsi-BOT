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
REDIRECT_URI = "http://localhost:5000/auth/discord/callback"

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
            user['guilds'] = app.bot.guilds
        else:
            user['guilds'] = [guild for guild in app.bot.guilds if guild.get_member(user['id'])]
        session['user'] = user
    if session['user'].get('guilds', None) is None:
        if session['user']['id'] == '708006478807695450':
            session['user']['guilds'] = app.bot.guilds
        else:
            session['user']['guilds'] = [guild for guild in app.bot.guilds if guild.get_member(session['user']['id'])]
    print(session['user'])
    return render_template('panel.html', servers=session['user']['guilds'], user=session['user'])


@app.route('/server/<int:server_id>', methods=['GET', 'POST'])
async def server(server_id):
    server_filename = os.path.join('queue', f'{server_id}.json')
    if server_id not in [guild.id for guild in app.bot.guilds]:
        return redirect(url_for('index'))

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
    return redirect('https://discord.com/oauth2/authorize?client_id=1167171085343666216&redirect_uri=http%3A%2F%2Flocalhost%3A5000%2Fauth%2Fdiscord%2Fcallback&response_type=code&scope=identify%20email%20guilds')

@app.route('/auth/discord/callback')
async def callback():
    code = request.args.get('code')
    token = await token_from_code(code)
    timer = Timer(token['expires_in'], refresh_token, [token['refresh_token']])
    timer.start()
    session['token'] = token
    session['timer'] = timer
    return redirect(url_for('panel'))


@app.route('/logout')
async def logout():
    session.pop('token', None)
    session.pop('user', None)
    await revoke_access_token(session['token']['access_token'])
    session['timer'].cancel()
    return redirect(url_for('index'))


async def token_from_code(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "http://localhost:5000/auth/discord/callback"
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
    session['timer'] = Timer(session['token']['expires_in'], refresh_token, [session['token']['refresh_token']])
    session['timer'].start()
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
