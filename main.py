import datetime
import os
import sys
import threading
import traceback
import argparse

from utils import CustomFormatter, GuildData, UserData, PanelToBotRequest, RequestType

import discord.utils
from discord.ext import tasks, commands
from dotenv import load_dotenv
import utils.config as config
import asyncio
from multiprocessing import Queue as mpQueue
import logging
from aiomultiprocess import Process

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


async def start_app(queue: mpQueue):
    from panel.panel import app
    app.set_queue(queue)
    await app.run_task(host="0.0.0.0", debug=False)
    


class Bot(commands.Bot):
    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.queue: mpQueue[PanelToBotRequest | GuildData | UserData | list[GuildData]] = mpQueue()

    async def on_ready(self):
        global start_time
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        p = Process(target=start_app, args=(self.queue,), name="Panel")
        p.start()
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update.start()
        threading.Thread(target=self.start_listening, name="Listener").start()
        logging.info(f"Bot ready in {datetime.datetime.now() - start_time}")
        for guild in self.guilds:
            # Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
            if not await config.Config.config_exists(guild.id):
                await config.Config.create_config(guild.id)

    def start_listening(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        future = asyncio.ensure_future(self.listen_to_queue())
        loop.run_until_complete(future)


    async def listen_to_queue(self):
        while True:
            if self.queue.empty():
                continue
            else:
                message = self.queue.get()
            if not isinstance(message, PanelToBotRequest):
                self.queue.put(message)
                continue
            match message.type:
                case RequestType.GET:
                    match message.content:
                        case "guilds":
                            guilds = []
                            if message.extra.get("user_id", None) is None or int(message.extra["user_id"]) == 708006478807695450:
                                guilds = [GuildData.from_guild(guild) for guild in self.guilds]
                            else:
                                guilds = [GuildData.from_guild(guild) for guild in self.guilds if int(message.extra["user_id"]) in [member.id for member in guild.members]]
                            logging.info("Got a request for all guilds of a user")
                            self.queue.put(guilds)
                            await asyncio.sleep(0.1)
                        case "guild":
                            guild = self.get_guild(int(message.extra["server_id"]))
                            guild = GuildData.from_guild(guild)
                            logging.info(f"Got a request for a specific guild : {message.extra['server_id']}")
                            self.queue.put(guild)
                            await asyncio.sleep(0.1)
                        case "user":
                            user = self.get_user(int(message.extra["user_id"]))
                            user = UserData.from_user(user)
                            logging.info(f"Got a request for a specific user : {message.extra['user_id']}")
                            self.queue.put(user)
                            await asyncio.sleep(0.1)
                        case _:
                            logging.error(f"Unknown request {message}")
                case RequestType.POST:
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
                       channel: discord.Option(discord.TextChannel, description="Le salon où envoyer le message"), # type: ignore
                       message: discord.Option(str, description="Le message à envoyer")):  # type: ignore
    if ctx.author.id != bot_instance.owner_id:
        raise commands.NotOwner
    await ctx.response.defer()
    channel = bot_instance.get_channel(channel)
    await channel.send(message)
    await ctx.respond(content="Message envoyé !", ephemeral=True)

@bot_instance.slash_command(name="stop-bot", description="Arrête le bot")
async def stop_bot(ctx: discord.ApplicationContext):
    if ctx.author.id != bot_instance.owner_id:
        raise commands.NotOwner
    await ctx.response.defer()
    await ctx.respond(content="Arrêt en cours...", ephemeral=True)
    await bot_instance.logout()
    await bot_instance.close()
    exit(0)


@send_message.error
async def send_message_error(ctx: discord.ApplicationContext, error: commands.CommandError):
    if isinstance(error, commands.NotOwner):
        await ctx.send("Vous n'êtes pas propriétaire du bot !", ephemeral=True)


def start(instance: Bot):
    # Charger les cogs
    global start_time
    os.system("cls" if os.name == "nt" else "clear")
    logging.info(
        f"Script started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
        f"using python executable {sys.executable}"
    )
    for file in os.listdir("./cogs"):
        if file.endswith(".py") and not file.startswith("__"):
            try:
                instance.load_extension(f"cogs.{file[:-3]}")
            except Exception as e:
                logging.error(f"Failed to load extension {file}")
                logging.error(e)
    
    # Lancer l'instance du bot
    instance.run(os.environ["TOKEN"])

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", type=str, default="INFO", help="The log level of the bot", required=False)
    return parser.parse_known_args()[0]

if __name__ == "__main__":
    # Les logs sont envoyés dans la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter(source="Bot"))
    log_level = getattr(logging, parse_args().log_level.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError(f"Invalid log level: {parse_args().log_level}")
    logging.basicConfig(level=log_level, handlers=[console_handler])
    if not os.path.exists("database/database.db"):
        if not os.path.exists("database/"):
            os.mkdir("database/")
        with open("database/database.db", "w") as f:
            f.write("")
        os.chdir("_others")
        os.system("python generate_db.py")
        os.chdir("..")
    start(bot_instance)
