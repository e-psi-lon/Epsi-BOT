import os
import sys
import discord
import asyncio
import traceback
import subprocess
from multiprocessing import Queue as mpQueue
from typing import Optional
from ..utils import GuildData, UserData, PanelBotRequest, PanelBotResponse, RequestType, get_logger, Event, set_callback, \
	Server, download_batch, AudioCache, Song, SongListenCount
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime

from .memcached_std import MemcachedStd

@tasks.loop(hours=5)
async def check_update() -> None:
	current_hash = os.popen("git rev-parse HEAD").read().strip()
	origin_hash = os.popen("git ls-remote origin main | awk '{print $1}'").read().strip()
	if current_hash != origin_hash:
		os.system("git pull")
		get_logger("Updater").info("Bot updated to the latest version")
		os.execl(sys.executable, sys.executable, *sys.argv)
	else:
		get_logger("Updater").info("Bot is already up to date")

@tasks.loop(hours=36)
async def update_top_songs(self: 'Bot') -> None:
		# Calculate top 5 songs
		top_songs: list[SongListenCount] = SongListenCount \
			.select()\
			.order_by(SongListenCount.count.desc())\
			.limit(5)\
			.prefetch(Song)

		top_songs_data = [
			{"name": song.song.name, "url": song.song.url, "listen_count": song.count}
			for song in top_songs
		]

		async with AudioCache(len(top_songs_data)) as cache:
			to_download = []
			# First update TTL for cached songs and collect uncached ones
			for song in top_songs_data:
				if await cache.exists(song["url"]):
					await cache.update_ttl(song["url"], 60*60*24*3)
				else:
					to_download.append(song["url"])
				
		# Batch download uncached songs
		if to_download:
			await download_batch(to_download)
		self.logger.info("Top 5 songs updated and cached.")
		# Reset listen counts
		SongListenCount.delete().execute()


class Bot(commands.Bot):
	def __init__(self, queue, event: Event, bot_event: Event, *args, **options) -> None:
		super().__init__(*args, **options)
		self.queue: mpQueue[PanelBotRequest | PanelBotResponse] = queue
		self.panel_event: Event = event
		self.event_listener: Event = bot_event
		self.memcached: Optional[subprocess.Popen] = None
		self.logger = get_logger("Bot")
		self.start_time: datetime

	async def on_ready(self) -> None:
		await self.change_presence(
			activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
		if os.popen("git branch --show-current").read().strip() == "main" and not check_update.is_running():
			check_update.start()
		await set_callback(self.event_listener, self.read_queue, self.loop)
		if self.memcached is None:
			try:
				# noinspection PyTypeChecker
				self.memcached = subprocess.Popen(
					args=["-d", "-p", "11211", "-I", "500m", "-m", "1024"],
					executable="/usr/bin/memcached",
					stdout=MemcachedStd(),
					stderr=MemcachedStd("stderr")
				)  # type: ignore[call-overload]
			except FileNotFoundError:
				self.logger.error("Memcached not found, please install it")
				self.memcached = None
				exit(1)
		self.logger.info(f"Bot ready in {datetime.now() - self.start_time}")
		for guild in self.guilds:
			# Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
			Server.get_or_create(server_id=guild.id)
		if not update_top_songs.is_running():
			update_top_songs.start(self)


	async def get_from_panel(self, content: str, **kwargs):
		data = PanelBotRequest.create(RequestType.GET, content, **kwargs)
		if self.queue is None:
			raise ValueError("Queue is not set")
		self.queue.put(data)
		await self.panel_event.set()
		self.logger.info(f"Getting {data} from panel")
		await self.event_listener.wait()
		response = self.queue.get()
		self.logger.info(f"Got {response} from panel")
		return response
	
	async def post_to_panel(self, data: dict | str):
		request_ = PanelBotRequest.create(RequestType.POST, data)  # type: ignore[arg-type]
		if self.queue is None:
			raise ValueError("Queue is not set")
		self.queue.put(request_)
		await self.panel_event.set()
		self.logger.info(f"Posting {request_} to panel")

	async def read_queue(self):
		message = self.queue.get()
		match message.type:
			case RequestType.GET:
				match message.content:
					case "guilds":
						if message.extra.get("user_id", None) is None or int(
								message.extra["user_id"]) == 708006478807695450:
							guilds = [GuildData.from_guild(guild) for guild in self.guilds]
						else:
							guilds = [GuildData.from_guild(guild) for guild in self.guilds if
										int(message.extra["user_id"]) in [member.id for member in guild.members]]
						self.logger.info("Got a request for all guilds of a user")
						self.queue.put(PanelBotResponse.create(RequestType.GET, guilds))
						await self.panel_event.set(True)
						await asyncio.sleep(0.1)
					case "guild":
						guild = self.get_guild(int(message.extra["server_id"]))
						guild = GuildData.from_guild(guild)
						self.logger.info(f"Got a request for a specific guild : {message.extra['server_id']}")
						self.queue.put(PanelBotResponse.create(RequestType.GET, guild))
						await self.panel_event.set(True)
						await asyncio.sleep(0.1)
					case "user":
						user = self.get_user(int(message.extra["user_id"]))
						user = UserData.from_user(user)
						self.logger.info(f"Got a request for a specific user : {message.extra['user_id']}")
						self.queue.put(PanelBotResponse.create(RequestType.GET, user))
						await self.panel_event.set(True)
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
							  color=discord.Color.dark_red())
		embed.add_field(name="Commande", value=f"`/{ctx.command}`")
		embed.add_field(name="Module", value=f"`{ctx.command.cog.__class__.__name__!r}`")
		embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
		embed.add_field(name="Traceback", value=f"```\n{traceback_str[:1014]}...```")
		try:
			await ctx.respond(embed=embed, ephemeral=True)
			await self.get_user(self.owner_id).send(embed=embed)  # type: ignore[union-attr]
		except discord.HTTPException:
			await ctx.channel.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)
			await self.get_user(self.owner_id).send(embed=embed)  # type: ignore[union-attr]

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
								  color=discord.Color.dark_red())
			embed.add_field(name="Commande", value=f"`{context.command}`")
			embed.add_field(name="Module", value=f"`{context.command.cog.__class__.__name__}`")
			embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
			embed.add_field(name="Traceback", value=f"```\n{traceback_str}```")
			try:
				await context.respond(embed=embed, ephemeral=True)
				await self.get_user(self.owner_id).send(embed=embed)  # type: ignore[union-attr]
			except discord.DiscordException:
				await context.send("Ce message se supprimera d'ici 20s", embed=embed, delete_after=20)
				await self.get_user(self.owner_id).send(embed=embed)  # type: ignore[union-attr]
		else:
			self.logger.error(
				f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
				f"\n Kwargs: {kwargs}")





async def start(instance: Bot, start_time: datetime):
	instance.start_time = start_time
	instance.owner_id = 708006478807695450
	@instance.slash_command(name="send", description="Envoie un message dans un salon")
	@discord.option("channel", discord.TextChannel, descritpion="Le salon où envoyer le message")
	@discord.option("message", str, description="Le message à envoyer")
	async def send_message(ctx: discord.ApplicationContext, channel: discord.TextChannel, message: str):
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
		if instance.memcached is not None:
			instance.memcached.terminate()
		await instance.post_to_panel("stop")


	@send_message.error
	async def send_message_error(ctx: discord.ApplicationContext, error: commands.CommandError):
		if isinstance(error, commands.NotOwner):
			await ctx.respond("Vous n'êtes pas propriétaire du bot !", ephemeral=True)

	# Charger les cogs
	instance.logger.info(
		f"Script started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
		f"using python executable {sys.executable}"
	)
	for file in os.listdir("./epsi_bot/cogs"):
		if file.endswith(".py") and not file.startswith("__"):
			try:
				instance.load_extension(f"epsi_bot.cogs.{file[:-3]}")
			except Exception as e:
				instance.logger.error(f"Failed to load extension {file}")
				instance.logger.error(e)

	# Lancer l'instance du bot
	try:
		token = os.getenv("TOKEN")
		if token is None:
			instance.logger.error("No token found, please set the environment variable TOKEN")
			exit(1)
		await instance.start(token)
	except KeyboardInterrupt:
		pass
	finally:
		await instance.close()
		if instance.memcached is not None:
			instance.memcached.terminate()