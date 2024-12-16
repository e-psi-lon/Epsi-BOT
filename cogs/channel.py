import asyncio
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands

from bot.bot import Bot
from utils import EMBED_ERROR_BOT_NOT_CONNECTED, play_song, check_video, Server


class Channel(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot

	@commands.slash_command(name="leave", description="Leaves the voice channel")
	async def leave(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		await ctx.guild.voice_client.disconnect(force=True)
		await ctx.respond(embed=discord.Embed(title="Leave", description="Bot left the voice channel.",
											  color=0x00ff00))
		server: Server = await Server.get(server_id=ctx.guild.id)
		server.queue = []
		server.position = 0
		server.save()

	@commands.slash_command(name='join', description='Join the voice channel you are in.')
	async def join(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is not None:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
															   "channel.", color=0xff0000))

		server: Server = Server.get(server_id=ctx.guild.id)
		if ctx.author.voice is None:
			return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
														 color=0xff0000))

		await ctx.author.voice.channel.connect()
		await ctx.respond(
			embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=0x00ff00))
		if server.queue:
			if server.position > len(server.queue) - 1:
				server.position = 0
				server.save()

			await play_song(ctx, server.queue[server.position].song.url)
			futures: list[asyncio.Future] = []
			if len(server.queue) > 1:
				with ThreadPoolExecutor() as pool:
					for queue_elem in server.queue[1:]:
						loop = asyncio.get_event_loop()
						futures.append(loop.run_in_executor(pool, check_video, self.bot, queue_elem.song, ctx, loop))
					for future in asyncio.as_completed(futures):
						try:
							await future
						except Exception as e:
							self.bot.logger.warning(f"Error while checking video: {e}")

def setup(bot: commands.Bot):
	bot.add_cog(Channel(bot))
