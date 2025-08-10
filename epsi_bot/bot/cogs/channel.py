import asyncio 
import discord
import pytubefix.exceptions  # type: ignore[import-untyped]
from discord.ext import commands
from epsi_bot.bot.bot import Bot
from epsi_bot.utils import EMBED_ERROR_BOT_NOT_CONNECTED, play_song, Server, download_bulk, get_youtube


class Channel(commands.Cog):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.description = "Voice channel related commands"

	@commands.slash_command(name="leave", description="Leaves the voice channel")
	async def leave(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		await ctx.guild.voice_client.disconnect(force=True)
		await ctx.respond(embed=discord.Embed(title="Leave", description="Bot left the voice channel.",
		                                      color=discord.Color.green()))
		server = await Server.get(server_id=ctx.guild.id)
		await server.queue.all().delete()
		server.position = 0
		await server.save()


	@commands.slash_command(name='join', description='Join the voice channel you are in.')
	async def join(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		if ctx.guild.voice_client is not None:
			await ctx.respond(
				embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
				                                               "channel.", color=discord.Color.dark_red())
			)
			return
		if isinstance(ctx.author, discord.User) or ctx.author.voice is None:
			await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
			                                             color=discord.Color.dark_red()))
			return
		if ctx.author.voice.channel is None:
			await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
			                                             color=discord.Color.dark_red()))
			return
		await ctx.author.voice.channel.connect()
		await ctx.respond(
			embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=discord.Color.green()))
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
		if await server.queue.all():
			if server.position > len(server.queue) - 1:
				server.position = 0
				await server.save()
			url = server.queue[server.position].song.url
			try:
				url = get_youtube(url).streams.get_audio_only().url
			except pytubefix.exceptions.RegexMatchError:
				pass
			await play_song(ctx, url, direct_play=True)
			queue = [queue.song.url for queue in server.queue]
			asyncio.create_task(download_bulk(queue))

def setup(bot: Bot) -> None:
	bot.add_cog(Channel(bot))
