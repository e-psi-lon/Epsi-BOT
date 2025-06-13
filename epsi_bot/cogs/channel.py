import discord
import pytubefix.exceptions
from discord.ext import commands

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import EMBED_ERROR_BOT_NOT_CONNECTED, play_song, Server, download_bulk, get_youtube


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
		server = await Server.get(server_id=ctx.guild.id)
		await server.queue.all().delete()
		server.position = 0
		await server.save()
		return None

	@commands.slash_command(name='join', description='Join the voice channel you are in.')
	async def join(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.guild.voice_client is not None:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
				                                               "channel.", color=discord.Color.dark_red())
			)
		if ctx.author.voice is None:
			return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
			                                             color=discord.Color.dark_red()))

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
			await download_bulk(queue)
		return None


def setup(bot: commands.Bot):
	bot.add_cog(Channel(bot))
