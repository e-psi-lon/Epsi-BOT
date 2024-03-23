import datetime
import os
import sys
import traceback

import dependencies_check
from utils.info_extractor import *

if __name__ == "__main__":
    if len(list(dependencies_check.check_libs())) > 0 and list(dependencies_check.check_libs())[0][0] != "pynacl":
        dependencies_check.update_libs([lib for lib, _, _ in dependencies_check.check_libs()])
        os.execl(sys.executable, sys.executable, *sys.argv)
import discord.utils
from discord.ext import tasks
from dotenv import load_dotenv
from panel.panel import *
import utils.config as config
import asyncio
import multiprocessing

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


def start_app(queue: multiprocessing.Queue):
    from panel.panel import app
    app.set_queue(queue)
    app.run(host="0.0.0.0")


class Bot(commands.Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.queue: multiprocessing.Queue = multiprocessing.Queue()

    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        p = multiprocessing.Process(target=start_app, args=(self.queue,), name="Panel")
        p.start()
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update.start()
        await asyncio.create_task(self.listen_to_queue())
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        for guild in self.guilds:
            # Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
            if not await config.Config.config_exists(guild.id):
                await config.Config.create_config(guild.id)

    async def listen_to_queue(self):
        while True:
            if self.queue.empty():
                await asyncio.sleep(1)
                continue
            else:
                message = self.queue.get()
            logging.info(f"Got a message from the queue : {message}")
            match message.get("type"):
                case "get":
                    match message.get("content"):
                        case "guilds":
                            logging.info("Got a request for all guilds")
                            self.queue.put([get_guild_info(guild) for guild in self.guilds])
                        case "guild":
                            logging.info(f"Got a request for a specific guild : {message}")
                            guild = self.get_guild(message["server_id"])
                            self.queue.put(get_guild_info(guild))
                        case "user":
                            logging.info(f"Got a request for a specific user : {message}")
                            user = self.get_user(message["user_id"])
                            self.queue.put(get_user_info(user))
                        case _:
                            pass
                case _:
                    pass

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        exc_type, exc_value, exc_traceback = type(error), error, error.__traceback__
        traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.error(f"Error in {ctx.command} from module {ctx.command.cog.__class__.__name__}"
                      f"\n Error message: {exc_value}\n Traceback: {traceback_str}")
        embed = discord.Embed(title="Une erreur est survenue", description=f"Erreur provoquée par {ctx.author.mention}",
                              color=discord.Color.red())
        embed.add_field(name="Commande", value=f"`/{ctx.command}`")
        embed.add_field(name="Module", value=f"`{ctx.command.cog.__class__.__name__!r}`")
        embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
        embed.add_field(name="Traceback", value=f"```\n{traceback_str[:1014]}...```")
        try:
            await ctx.respond(embed=embed, ephemeral=True)
        except Exception:
            await ctx.channel.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        context = None
        for arg in args:
            if isinstance(arg, discord.ApplicationContext):
                context = arg
                break
        if not context:
            for arg in kwargs.values():
                if isinstance(arg, discord.ApplicationContext):
                    context = arg
                    break
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        if context is not None:
            logging.error(
                f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
                f"\n Kwargs: {kwargs}")
            embed = discord.Embed(title="Une erreur est survenue",
                                  description=f"Erreur provoquée par {context.author.mention}",
                                  color=discord.Color.red())
            embed.add_field(name="Commande", value=f"`{context.command}`")
            embed.add_field(name="Module", value=f"`{context.command.cog.__class__.__name__}`")
            embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
            embed.add_field(name="Traceback", value=f"```\n{traceback_str}```")
            try:
                await context.respond(embed=embed, ephemeral=True)
            except Exception:
                await context.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)
        else:
            logging.error(
                f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
                f"\n Kwargs: {kwargs}")


bot_instance = Bot(intents=discord.Intents.all())
bot_instance.owner_id = 708006478807695450


@bot_instance.slash_command(name="send", description="Envoie un message dans un salon")
async def send_message(ctx: discord.ApplicationContext,
                       channel: discord.Option(discord.TextChannel, description="Le salon où envoyer le message"),
                       # type: ignore
                       message: discord.Option(str, description="Le message à envoyer")):  # type: ignore
    if ctx.author.id != bot_instance.owner_id:
        raise commands.NotOwner
    await ctx.response.defer()
    channel = bot_instance.get_channel(channel)
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
    start(bot_instance)
