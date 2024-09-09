import os
import sys
import discord
import asyncio
import datetime
import traceback
import subprocess
from multiprocessing import Queue as mpQueue
from typing import Optional
from utils import GuildData, UserData, PanelBotReqest, PanelBotResponse, RequestType, config, get_logger, Event, set_callback
from discord.ext import commands
from discord.ext import tasks

from .memcached_std import MemcachedStd

@tasks.loop(hours=5)
async def check_update():
    current_hash = os.popen("git rev-parse HEAD").read().strip()
    origin_hash = os.popen("git ls-remote origin main | awk '{print $1}'").read().strip()
    if current_hash != origin_hash:
        os.system("git pull")
        get_logger("Updater").info("Bot updated to the latest version")
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        get_logger("Updater").info("Bot is already up to date")


class Bot(commands.Bot):
    def __init__(self, queue, event, bot_event, *args, **options):
        super().__init__(*args, **options)
        self.queue: mpQueue[PanelBotReqest | PanelBotResponse] = queue
        self.panel_event: Event = event
        self.event_listener: Event = bot_event
        self.memcached: Optional[subprocess.Popen] = None
        self.logger = get_logger("Bot")
        self.start_time: Optional[datetime.datetime] = None

    async def on_ready(self):
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
        if os.popen("git branch --show-current").read().strip() == "main":
            check_update.start()
        set_callback(self.event_listener, self.read_queue(), self.loop)
        if os.name == "nt":
            self.memcached = subprocess.Popen(["wsl", "memcached", "d", "-p", "11211", "-I", "500m", "-m", "1024"], stdout=MemcachedStd(), stderr=MemcachedStd("stderr"))
        else:
            try:
                self.memcached = subprocess.Popen(["memcached", "-d", "-p", "11211", "-I", "500m", "-m", "1024"], stdout=MemcachedStd(), stderr=MemcachedStd("stderr"))
            except FileNotFoundError:
                self.logger.error("Memcached not found, please install it")
                self.memcached = None
                exit(1)
        self.logger.info(f"Bot ready in {datetime.datetime.now() - self.start_time}")
        for guild in self.guilds:
            # Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
            if not await config.Config.config_exists(guild.id):
                await config.Config.create_config(guild.id)

    async def get_from_panel(self, content: str, **kwargs):
        data = PanelBotReqest.create(RequestType.GET, content, **kwargs)
        if self.queue is None:
            raise ValueError("Queue is not set")
        self.queue.put(data)
        self.panel_event.set()
        self.logger.info(f"Getting {data} from panel")
        await self.event_listener.wait()
        response = self.queue.get()
        self.logger.info(f"Got {response} from panel")
        return response
    
    async def post_to_panel(self, data: dict | str):
        request_ = PanelBotReqest.create(RequestType.POST, data)
        if self.queue is None:
            raise ValueError("Queue is not set")
        self.queue.put(request_)
        self.panel_event.set()
        self.logger.info(f"Posting {request_} to panel")

    async def read_queue(self):
        message = self.queue.get()
        match message.type:
            case RequestType.GET:
                match message.content:
                    case "guilds":
                        guilds = []
                        if message.extra.get("user_id", None) is None or int(
                                message.extra["user_id"]) == 708006478807695450:
                            guilds = [GuildData.from_guild(guild) for guild in self.guilds]
                        else:
                            guilds = [GuildData.from_guild(guild) for guild in self.guilds if
                                        int(message.extra["user_id"]) in [member.id for member in guild.members]]
                        self.logger.info("Got a request for all guilds of a user")
                        self.queue.put(PanelBotResponse.create(RequestType.GET, guilds))
                        self.panel_event.set(True)
                        await asyncio.sleep(0.1)
                    case "guild":
                        guild = self.get_guild(int(message.extra["server_id"]))
                        guild = GuildData.from_guild(guild)
                        self.logger.info(f"Got a request for a specific guild : {message.extra['server_id']}")
                        self.queue.put(PanelBotResponse.create(RequestType.GET, guild))
                        self.panel_event.set(True)
                        await asyncio.sleep(0.1)
                    case "user":
                        user = self.get_user(int(message.extra["user_id"]))
                        user = UserData.from_user(user)
                        self.logger.info(f"Got a request for a specific user : {message.extra['user_id']}")
                        self.queue.put(PanelBotResponse.create(RequestType.GET, user))
                        self.panel_event.set(True)
                        await asyncio.sleep(0.1)
                    case _:
                        self.logger.error(f"Unknown request {message}")
            case RequestType.POST:
                pass

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        exc_type, exc_value, exc_traceback = type(error), error, error.__traceback__
        traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.logger.error(f"Error in {ctx.command} from module {ctx.command.cog.__class__.__name__}"
                      f"\n Error message: {exc_value}\n Traceback: {traceback_str}")
        embed = discord.Embed(title="Une erreur est survenue", description=f"Erreur provoquée par {ctx.author.mention}",
                              color=discord.Color.red())
        embed.add_field(name="Commande", value=f"`/{ctx.command}`")
        embed.add_field(name="Module", value=f"`{ctx.command.cog.__class__.__name__!r}`")
        embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
        embed.add_field(name="Traceback", value=f"```\n{traceback_str[:1014]}...```")
        try:
            await ctx.respond(embed=embed, ephemeral=True)
            await self.get_user(self.owner_id).send(embed=embed)
        except discord.HTTPException:
            await ctx.channel.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)
            await self.get_user(self.owner_id).send(embed=embed)

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
            self.logger.error(
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
                await self.get_user(self.owner_id).send(embed=embed)
            except discord.DiscordException:
                await context.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)
                await self.get_user(self.owner_id).send(embed=embed)
        else:
            self.logger.error(
                f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
                f"\n Kwargs: {kwargs}")





async def start(instance: Bot, start_time: datetime.datetime):
    instance.start_time = start_time
    instance.owner_id = 708006478807695450
    @instance.slash_command(name="send", description="Envoie un message dans un salon")
    @discord.option("channel", discord.TextChannel, descritpion="Le salon où envoyer le message")
    @discord.option("message", str, description="Le message à envoyer")
    async def send_message(ctx: discord.ApplicationContext,
                        channel: discord.TextChannel,
                        message: str):
        if ctx.author.id != instance.owner_id:
            raise commands.NotOwner
        await ctx.response.defer()
        await channel.send(message)
        await ctx.respond(content="Message envoyé !", ephemeral=True)


    @instance.slash_command(name="stop-bot", description="Arrête le bot")
    async def stop_bot(ctx: discord.ApplicationContext):
        if ctx.author.id != instance.owner_id:
            raise commands.NotOwner
        await ctx.response.defer()
        await ctx.respond(content="Arrêt en cours...", ephemeral=True)
        await instance.close()
        instance.memcached.terminate()
        instance.post_to_panel("stop")


    @send_message.error
    async def send_message_error(ctx: discord.ApplicationContext, error: commands.CommandError):
        if isinstance(error, commands.NotOwner):
            await ctx.respond("Vous n'êtes pas propriétaire du bot !", ephemeral=True)

    # Charger les cogs
    instance.logger.info(
        f"Script started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
        f"using python executable {sys.executable}"
    )
    for file in os.listdir("./cogs"):
        if file.endswith(".py") and not file.startswith("__"):
            try:
                instance.load_extension(f"cogs.{file[:-3]}")
            except Exception as e:
                instance.logger.error(f"Failed to load extension {file}")
                instance.logger.error(e)

    # Lancer l'instance du bot
    try:
        await instance.start(os.getenv("TOKEN"))
    except KeyboardInterrupt:
        pass
    finally:
        await instance.close()
        instance.memcached.terminate()