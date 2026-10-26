import asyncio

import discord
import pytubefix.exceptions
from discord.ext import commands

from epsi_bot.bot.bot import Bot
from epsi_bot.utils.audio import get_youtube, play_song
from epsi_bot.utils.cache import download_bulk
from epsi_bot.utils.constants import EMBED_ERROR_BOT_NOT_CONNECTED
from epsi_bot.utils.models import Server
from epsi_bot.utils.type_utils import get_guild


class Channel(commands.Cog):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.description = "Voice channel related commands"

	@commands.slash_command(name="leave", description="Leaves the voice channel")
	async def leave(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if (voice_client := guild.voice_client) is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		await voice_client.disconnect(force=True)
		await ctx.respond(
			embed=discord.Embed(
				title="Leave",
				description="Bot left the voice channel.",
				color=discord.Color.green(),
			)
		)
		server = await Server.get(server_id=guild.id)
		await server.queue.all().delete()
		server.position = 0
		await server.save()

	@commands.slash_command(
		name="join", description="Join the voice channel you are in."
	)
	async def join(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		guild = get_guild(ctx)
		if guild.voice_client is not None:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="Bot is already connected to a voice channel.",
					color=discord.Color.dark_red(),
				)
			)
			return
		if (
			isinstance(author := ctx.author, discord.User)
			or (voice := author.voice) is None
		):
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="You must be in a voice channel.",
					color=discord.Color.dark_red(),
				)
			)
			return
		if voice.channel is None:
			await ctx.respond(
				embed=discord.Embed(
					title="Error",
					description="You must be in a voice channel.",
					color=discord.Color.dark_red(),
				)
			)
			return
		await voice.channel.connect()
		await ctx.respond(
			embed=discord.Embed(
				title="Join",
				description="Bot joined the voice channel.",
				color=discord.Color.green(),
			)
		)
		server = await Server.get(server_id=guild.id).prefetch_related(
			"queue", "queue__song"
		)
		if await server.queue.all():
			if server.position > len(server.queue) - 1:
				server.position = 0
				await server.save()
			url = server.queue[server.position].song.url
			try:
				stream = get_youtube(url).streams.get_audio_only()
				if stream is None:
					raise ValueError("No audio stream found")
				url = stream.url
			except pytubefix.exceptions.RegexMatchError, ValueError:
				pass
			await play_song(ctx, url, direct_play=True)
			queue = [queue.song.url for queue in server.queue]
			asyncio.create_task(download_bulk(queue))


def setup(bot: Bot) -> None:
	bot.add_cog(Channel(bot))
