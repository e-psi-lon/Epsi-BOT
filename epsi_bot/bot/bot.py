import asyncio
import pkgutil
import sys
import traceback
from collections.abc import Callable, Coroutine, Iterable
from datetime import UTC, datetime
from typing import Any, cast

import discord
from discord.ext import commands, tasks
from discord.ext.commands import when_mentioned
from discord.utils import get_or_fetch

from epsi_bot.bot import cogs
from epsi_bot.panel.panel_base import PanelBase
from epsi_bot.utils.cache import AudioCache, download_bulk
from epsi_bot.utils.loggers import get_logger
from epsi_bot.utils.models import Server, SongListenCount
from epsi_bot.utils.type_utils import get_channel


@tasks.loop(hours=36)
async def update_top_songs(self: Bot) -> None:
	# Calculate top 5 songs
	top_songs = (
		await SongListenCount.all().prefetch_related("song").order_by("-count").limit(5)
	)
	top_songs_data = [
		{"name": song.song.name, "url": song.song.url, "listen_count": song.count}
		for song in top_songs
	]
	await SongListenCount.all().delete()
	to_download: list[str]
	async with AudioCache(len(top_songs_data)) as cache:
		to_download = []
		# First update TTL for cached songs and collect uncached ones
		for song in top_songs_data:
			if not isinstance(song["url"], str):
				self.logger.warning(f"Invalid URL for song {song['name']}, skipping.")
				continue
			if await cache.exists(song["url"]):
				await cache.update_ttl(song["url"], 60 * 60 * 24 * 3)
			else:
				to_download.append(song["url"])

	# Bulk download uncached songs
	if to_download:
		await download_bulk(to_download)
	self.logger.info("Top 5 songs updated and cached.")


class Bot(commands.Bot):
	owner_id: int

	def __init__(
		self,
		command_prefix: str
		| Iterable[str]
		| Callable[
			[commands.Bot | commands.AutoShardedBot, discord.Message],
			str | Iterable[str] | Coroutine[Any, Any, str | Iterable[str]],
		] = when_mentioned,
		help_command: commands.HelpCommand | None = discord.utils.MISSING,
		**options: Any,
	) -> None:
		super().__init__(command_prefix, help_command, **options)
		self.start_time: datetime | None = None
		self.logger = get_logger("Bot")
		self.panel: PanelBase | None = None
		self._load_cogs()
		self._shutdown_event: asyncio.Event | None = None

	@property
	def shutdown_event(self) -> asyncio.Event:
		if self._shutdown_event is None:
			raise RuntimeError("Bot shutdown event not initialized")
		return self._shutdown_event

	def _load_cogs(self) -> None:
		names = [
			m.name
			for m in pkgutil.iter_modules(cogs.__path__, prefix=f"{cogs.__name__}.")
			if not m.name.rsplit(".", 1)[-1].startswith("_")
		]
		results = cast(
			dict[str, bool | Exception], self.load_extensions(*names, store=True)
		)
		for name, result in results.items():
			if result is not True:
				self.logger.error("Failed to load extension %s", name, exc_info=result)

	async def on_ready(self) -> None:
		await self.change_presence(
			activity=discord.Activity(
				type=discord.ActivityType.watching,
				name=f"/help | {len(self.guilds)} servers",
			)
		)
		if self.start_time is not None:
			self.logger.info(f"Bot ready in {datetime.now(UTC) - self.start_time}")
		for guild in self.guilds:
			# If the guild doesn't exist in the db, we add it with default parameters
			await Server.get_or_create(server_id=guild.id)
		if not update_top_songs.is_running():
			update_top_songs.start(self)

	async def on_application_command_error(
		self, context: discord.ApplicationContext, exception: discord.DiscordException
	) -> None:
		exc_type, exc_value, exc_traceback = (
			type(exception),
			exception,
			exception.__traceback__,
		)
		traceback_str = "".join(
			traceback.format_exception(exc_type, exc_value, exc_traceback)
		)
		cog_name: str
		if (command := context.command) is not None:
			cog_name = command.cog.__class__.__name__
		else:
			cog_name = "None"
		self.logger.error(
			f"Error in {context.command} from module {cog_name}"
			f"\n Error message: {exc_value}\n Traceback: {traceback_str}"
		)
		embed = discord.Embed(
			title="Une erreur est survenue",
			description=f"Erreur provoquée par {context.author.mention}",
			color=discord.Color.dark_red(),
		)
		embed.add_field(name="Commande", value=f"`/{context.command}`")
		embed.add_field(name="Module", value=f"`{cog_name!r}`")
		embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
		embed.add_field(name="Traceback", value=f"```\n{traceback_str[:1014]}...```")
		try:
			await context.respond(embed=embed, ephemeral=True)
			await (await get_or_fetch(self, discord.User, self.owner_id)).send(
				embed=embed
			)
		except discord.HTTPException:
			try:
				channel = get_channel(context)
				if isinstance(channel, discord.abc.Messageable):
					await channel.send(
						"Ce message se supprimera d'ici 20s",
						embed=embed,
						delete_after=20,
					)
			except commands.ChannelNotFound:
				pass
			await (await get_or_fetch(self, discord.User, self.owner_id)).send(
				embed=embed
			)

	async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
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
		traceback_str = "".join(
			traceback.format_exception(exc_type, exc_value, exc_traceback)
		)
		if context is not None:
			self.logger.error(
				f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
				f"\n Kwargs: {kwargs}"
			)
			embed = discord.Embed(
				title="Une erreur est survenue",
				description=f"Erreur provoquée par {context.author.mention}",
				color=discord.Color.dark_red(),
			)
			if (command := context.command) is None:
				embed.add_field(
					name="Commande", value="Aucune commande n'a été exécutée"
				)
			else:
				embed.add_field(name="Commande", value=f"`{command}`")
				embed.add_field(
					name="Module", value=f"`{command.cog.__class__.__name__}`"
				)
			embed.add_field(name="Message d'erreur", value=f"`{exc_value}`")
			embed.add_field(name="Traceback", value=f"```\n{traceback_str}```")
			try:
				await context.respond(embed=embed, ephemeral=True)
				await (await get_or_fetch(self, discord.User, self.owner_id)).send(
					embed=embed
				)
			except discord.DiscordException:
				await context.send(
					"Ce message se supprimera d'ici 20s", embed=embed, delete_after=20
				)
				await (await get_or_fetch(self, discord.User, self.owner_id)).send(
					embed=embed
				)
		else:
			self.logger.error(
				f"Error in {event_method}\n Error message: {exc_value}\n Traceback: {traceback_str}\n Args: {args}"
				f"\n Kwargs: {kwargs}"
			)

	def get_guilds_for(self, user_id: int) -> list[discord.Guild]:
		return [
			guild
			for guild in self.guilds
			if user_id == self.owner_id
			or user_id is None
			or user_id in [member.id for member in guild.members]
		]
