import datetime
import multiprocessing
from multiprocessing.connection import Connection
import os
import sys
import dependencies_check
import threading
if __name__ == "__main__":
    if len(list(dependencies_check.check_libs())) > 0 and list(dependencies_check.check_libs())[0][0] != "pynacl":
        dependencies_check.update_libs([lib for lib, _, _ in dependencies_check.check_libs()])
        os.execl(sys.executable, sys.executable, *sys.argv)
import discord.utils
from utils import *
from discord.ext import tasks
from dotenv import load_dotenv
from panel.panel import *

load_dotenv()


@tasks.loop(seconds=18000)
async def check_update():
    current_hash = os.popen("git rev-parse HEAD").read().strip()
    origin_hash = os.popen("git ls-remote origin main | awk '{print $1}'").read().strip()
    if current_hash != origin_hash:
        os.system("git pull")
        logging.info("Bot updated to the latest version")
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        logging.info("Bot is already up to date")


def start_app(conn: Connection):
    from panel.panel import app
    app.set_connection(conn)
    app.run(host="0.0.0.0")
    conn.close()


class Bot(commands.Bot):
    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        # pour pouvoir lancer le serveur web
        parent_conn, child_conn = multiprocessing.Pipe()
        p = multiprocessing.Process(target=start_app, args=(child_conn,), name="Panel")
        p.start()
        self.conn = parent_conn
        # On verifie si on est sur main ou sur dev ou une autre branche
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update.start()
        threading.Thread(target=listen_to_conn, args=(self,), name="Connection-Listener").start()
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        self.help_command = commands.DefaultHelpCommand()


def listen_to_conn(bot: Bot):
    while True:
        message = bot.conn.recv()   
        match message:
            case {"type": "get", "content": "guilds"}:
                logging.info("Got a request for all guilds")
                bot.conn.send([{
                    "name": guild.name,
                    "id": guild.id,
                    "icon": "" if not hasattr(guild.icon, "url") else guild.icon.url,
                    "members": [{
                        "name": member.name,
                        "global_name": member.global_name,
                        "id": member.id,
                        "avatar": "" if not hasattr(member.avatar, "url") else member.avatar.url
                    } for member in guild.members],
                    "channels": [{
                        "name": channel.name,
                        "id": channel.id,
                        "type": channel.type.name
                    } for channel in guild.channels]
                } for guild in bot.guilds])
            case {"type": "get", "content": "guild"}:
                logging.info(f"Got a request for a specific guild : {message}")
                guild = bot.get_guild(message["server_id"])
                bot.conn.send({
                    "name": guild.name,
                    "id": guild.id,
                    "icon": "" if not hasattr(guild.icon, "url") else guild.icon.url,
                    "members": [{
                        "name": member.name,
                        "global_name": member.global_name,
                        "id": member.id,
                        "avatar": "" if not hasattr(member.avatar, "url") else member.avatar.url
                    } for member in guild.members],
                    "channels": [{
                        "name": channel.name,
                        "id": channel.id,
                        "type": channel.type.name
                    } for channel in guild.channels]
                })
            case {"type": "get", "content": "user"}:
                logging.info(f"Got a request for a specific user : {message}")
                user = bot.get_user(message["user_id"])
                bot.conn.send({
                    "name": user.name,
                    "global_name": user.global_name,
                    "id": user.id,
                    "avatar": "" if not hasattr(user.avatar, "url") else user.avatar.url
                })
            case _:
                pass


bot = Bot(intents=discord.Intents.all())
bot.owner_id = 708006478807695450


@bot.slash_command(name="help", description="Affiche l'aide du bot", guild_ids=[812807444698549862])
async def _help(ctx):
    await ctx.response.defer()
    mapping = bot.get_bot_mapping()
    embeds = bot.send_bot_help(mapping)
    await ctx.respond(embeds=embeds)


@bot.slash_command(name="send", description="Envoie un message dans un salon")
async def send_message(ctx: discord.ApplicationContext, channel: discord.Option(discord.TextChannel, description="Le salon où envoyer le message"), message: discord.Option(str, description="Le message à envoyer")):
    if ctx.author.id != bot.owner_id:
        raise commands.NotOwner
    await ctx.response.defer()
    channel = bot.get_channel(channel)
    await channel.send(message)
    await ctx.respond(content="Message envoyé !", ephemeral=True)


@send_message.error
async def send_message_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("Vous n'êtes pas propriétaire du bot !", ephemeral=True)

def start(instance: Bot):
    # Charger les cogs
    global start_time
    if not os.path.exists('cache/'):
        os.mkdir('cache/')
    cogs = [
        "cogs.channel",
        "cogs.others",
        "cogs.playlist",
        "cogs.queue_related",
        "cogs.state",
        "cogs.todo",
        "cogs.admin",
        "cogs.listeners"
    ]
    os.system("cls" if os.name == "nt" else "clear")
    start_time = datetime.datetime.now()
    logging.info(
        f"Script started at {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} using python executable {sys.executable}")
    if len(list(dependencies_check.check_updates())) > 0:
        dependencies_check.update_requirements()
        logging.info("Requirements updated")
    if len(list(dependencies_check.check_libs())) > 0:
        dependencies_check.update_libs([lib for lib, _, _ in dependencies_check.check_libs()])
        logging.info("Libs updated")
    for cog in cogs:
        try:
            instance.load_extension(cog)
        except Exception as e:
            logging.error(f"Failed to load extension {cog}")
            logging.error(e)
    # Lancer l'instance du bot
    instance.run(os.environ["TOKEN"])


if __name__ == "__main__":
    # Les logs sont envoyés dans la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter(source="Bot"))
    logging.basicConfig(level=logging.INFO, handlers=[console_handler])
    if not os.path.exists("database/database.db"):
        os.mkdir("database/")
        with open("database/database.db", "w") as f:
            f.write("")
        os.chdir("_others")
        os.system("python generate_db.py")
        os.chdir("..")
    start(bot)
