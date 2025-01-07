import discord
from discord.ext import commands

from ..bot.bot import Bot
from ..utils import EMBED_ERROR_BOT_NOT_CONNECTED, play_song, Server, download_batch


class Channel(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Voice channel related commands"

	@commands.slash_command(name="leave", description="Leaves the voice channel")
	async def leave(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		await ctx.guild.voice_client.disconnect(force=True)
		await ctx.respond(embed=discord.Embed(title="Leave", description="Bot left the voice channel.",
											  color=discord.Color.green()))
		server: Server = Server.get(server_id=ctx.guild.id)
		server.queue = []
		server.position = 0
		server.save()

	@commands.slash_command(name='join', description='Join the voice channel you are in.')
	async def join(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is not None:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
															   "channel.", color=discord.Color.dark_red())
			)
		server: Server = Server.get(server_id=ctx.guild.id)
		if ctx.author.voice is None:
			return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
														 color=discord.Color.dark_red()))

		await ctx.author.voice.channel.connect()
		await ctx.respond(
			embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=discord.Color.green()))
		if server.queue:
			if server.position > len(server.queue) - 1:
				server.position = 0
				server.save()
			await play_song(ctx, server.queue[server.position].song.url)
			if len(server.queue) > 1:
				queue = [queue.song.url for queue in server.queue[1:]]
				await download_batch(queue[1:])
def setup(bot: commands.Bot):
	bot.add_cog(Channel(bot))
