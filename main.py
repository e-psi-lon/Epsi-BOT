import datetime
import multiprocessing
import os
import sys
import dependencies_check
import threading
import traceback

if __name__ == "__main__":
    if len(list(dependencies_check.check_libs())) > 0 and list(dependencies_check.check_libs())[0][0] != "pynacl":
        dependencies_check.update_libs([lib for lib, _, _ in dependencies_check.check_libs()])
        os.execl(sys.executable, sys.executable, *sys.argv)
import discord.utils
from discord.ext import tasks
from dotenv import load_dotenv
from panel.panel import *
import utils.config as config

load_dotenv()

start_time = datetime.datetime.now()


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


class Bot(commands.Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.conn = None

    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        if not self.conn:
            parent_conn, child_conn = multiprocessing.Pipe()
            p = multiprocessing.Process(target=start_app, args=(child_conn,), name="Panel")
            p.start()
            self.conn = parent_conn
            if os.popen("git branch --show-current").read().strip() == "main":
                check_update.start()
            threading.Thread(target=listen_to_conn, args=(self,), name="Connection-Listener").start()
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        for guild in self.guilds:
            # Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
            if not await config.Config.config_exists(guild.id):
                await config.Config.create_config(guild.id)

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        logging.error(f"Error in {ctx.command}: {error}")

        embed = discord.Embed(title="Une erreur est survenue", description=f"Erreur provoquée par {ctx.author.mention}",
                              color=discord.Color.red())
        command = ctx.command
        command_path = []
        while command.parent:
            command_path.append(command.name)
            command = command.parent
        embed.add_field(name="Commande", value=f"`/{''.join(reversed(command_path))}`")
        embed.add_field(name="Module", value=f"`{ctx.command.cog.__class__.__name__!r}`")
        embed.add_field(name="Message d'erreur", value=f"`{error}`")
        embed.add_field(name="Traceback", value=f"```\n{error.__traceback__}```")
        await ctx.channel.send("Ce message se supprimera d'ici 60s", embed=embed, delete_after=60)

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        ctx = None
        for arg in args:
            if isinstance(arg, discord.ApplicationContext):
                ctx = arg
                break
        if not ctx:
            for arg in kwargs.values():
                if isinstance(arg, discord.ApplicationContext):
                    ctx = arg
                    break
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        if ctx is not None:
            logging.error(
                f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}\n Kwargs: {kwargs}")
            embed = discord.Embed(title="Une erreur est survenue",
                                  description=f"Erreur provoquée par {ctx.author.mention}",
                                  color=discord.Color.red())
            embed.add_field(name="Commande", value=f"`{ctx.command}`")
            embed.add_field(name="Module", value=f"`{ctx.command.cog.__class__.__name__}`")
            embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
            embed.add_field(name="Traceback", value=f"```\n{traceback_str}```")
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            logging.error(
                f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}\n Kwargs: {kwargs}")


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
async def send_message(ctx: discord.ApplicationContext,
                       channel: discord.Option(discord.TextChannel, description="Le salon où envoyer le message"),
                       # type: ignore
                       message: discord.Option(str, description="Le message à envoyer")):  # type: ignore
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
    logging.info(
        f"Script started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
        f"using python executable {sys.executable}")
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
        if not os.path.exists("database/"):
            os.mkdir("database/")
        with open("database/database.db", "w") as f:
            f.write("")
        os.chdir("_others")
        os.system("python generate_db.py")
        os.chdir("..")
    start(bot)
