import os
import subprocess
import sys
import traceback
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands
from discord.ext import tasks
from tortoise import Tortoise, connections

from epsi_bot.bot.memcached_std import MemcachedStd
from epsi_bot.utils import GuildData, UserData, get_logger, \
	Server, download_bulk, AudioCache, SongListenCount, models
from epsi_bot.utils.ipc import IPCManager
from epsi_bot.utils.models import get_db_url


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
	await Tortoise.init(
		db_url=get_db_url(),
		modules={'models': [models]}
	)
	top_songs = await SongListenCount.all() \
		.prefetch_related("song") \
		.order_by("-count") \
		.limit(5)
	top_songs_data = [
		{"name": song.song.name, "url": song.song.url, "listen_count": song.count}
		for song in top_songs
	]
	await SongListenCount.all().delete()
	await connections.close_all()
	async with AudioCache(len(top_songs_data)) as cache:
		to_download = []
		# First update TTL for cached songs and collect uncached ones
		for song in top_songs_data:
			if await cache.exists(song["url"]):
				cache.update_ttl(song["url"], 60 * 60 * 24 * 3)
			else:
				to_download.append(song["url"])

	# Bulk download uncached songs
	if to_download:
		await download_bulk(to_download)
	self.logger.info("Top 5 songs updated and cached.")


class Bot(commands.Bot):
	def __init__(self, manager: IPCManager, *args, **options) -> None:
		super().__init__(*args, **options)
		self.start_time = None
		self.ipc: IPCManager = manager
		self.memcached: Optional[subprocess.Popen] = None
		self.logger = get_logger("Bot")
		self.start_time: datetime
		self.handle = self.ipc.handle
		self.post_to_panel = self.ipc.send
		self.get_from_panel = self.ipc.request

	async def on_ready(self) -> None:
		await self.change_presence(
			activity=discord.Activity(type=discord.ActivityType.watching, name=f"/help | {len(self.guilds)} servers"))
		if os.popen("git branch --show-current").read().strip() == "main" and not check_update.is_running():
			check_update.start()
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
		await Tortoise.init(
			db_url=get_db_url(),
			modules={'models': [models]}
		)
		await Tortoise.generate_schemas(safe=True)
		for guild in self.guilds:
			# Si la guilde n'existe pas dans la db, on l'ajoute avec les paramètres par défaut
			await Server.get_or_create(server_id=guild.id)
		await connections.close_all()
		if not update_top_songs.is_running():
			update_top_songs.start(self)

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

	db_logger = get_logger("Database")

	@instance.before_invoke
	async def before_invoke(_: commands.Context):
		await Tortoise.init(
			db_url=get_db_url(),
			modules={'models': [models]}
		)
		# noinspection PyProtectedMember
		db_logger.debug("Tortoise-ORM started, %s, %s", connections._get_storage(), Tortoise.apps)

	@instance.after_invoke
	async def after_invoke(_: commands.Context):
		await connections.close_all()
		db_logger.info("Tortoise-ORM shutdown")

	@instance.handle("guilds")
	async def handle_guilds(request_id: str, user_id: Optional[int] = None):
		if user_id is None or user_id == 708006478807695450:
			guilds = [GuildData.from_guild(guild) for guild in instance.guilds]
		else:
			guilds = [GuildData.from_guild(guild) for guild in instance.guilds if
			          user_id in [member.id for member in guild.members]]
		instance.logger.debug("Got a request for all guilds of a user")
		await instance.ipc.respond(request_id, guilds)

	@instance.handle("guild")
	async def handle_guild(request_id: str, server_id: int):
		guild = instance.get_guild(server_id)
		guild = GuildData.from_guild(guild)
		instance.logger.debug(f"Got a request for a specific guild : {server_id}")
		await instance.ipc.respond(request_id, guild)

	@instance.handle("user")
	async def handle_user(request_id: str, user_id: int):
		user = instance.get_user(user_id)
		user = UserData.from_user(user)
		instance.logger.debug(f"Got a request for a specific user : {user_id}")
		await instance.ipc.respond(request_id, user)

	@instance.handle("connected_servers")
	async def handle_connected_servers(request_id: str):
		server_count = len(instance.guilds)
		instance.logger.debug("Got a request for connected servers count")
		await instance.ipc.respond(request_id, server_count)

	@instance.handle("voice_channels")
	async def handle_voice_channels(request_id: str):
		active_voice = sum(
			1 for guild in instance.guilds for vc in guild.voice_channels if len(vc.members) > 0
		)
		instance.logger.debug("Got a request for active voice channels count")
		await instance.ipc.respond(request_id, active_voice)

	# Charger les cogs
	instance.logger.info(
		f"Bot started at {start_time.strftime('%d/%m/%Y %H:%M:%S')} "
		f"using python executable {sys.executable}"
	)
	for file in os.listdir("./epsi_bot/bot/cogs"):
		if file.endswith(".py") and not file.startswith("__"):
			try:
				instance.load_extension(f"epsi_bot.bot.cogs.{file[:-3]}")
			except Exception as e:
				instance.logger.error(f"Failed to load extension {file}")
				instance.logger.error(e)

	await instance.ipc.start()
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
