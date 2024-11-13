import asyncio

import discord
from discord.ext import commands

from utils import Config, OWNER_ID, Base64Serializer, EMBED_ERROR_NOT_BOT_OWNER
from aiocache import MemcachedCache

removed_count = 0


class Admin(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	@commands.slash_command(name="remove_cache", description="Removes the audio cache", guild_ids=[761485410596552736])
	async def remove_cache(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.author.id != OWNER_ID:
			return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
		temp_config = await Config.get_config(ctx.guild.id, False)
		temp_config2 = await Config.get_config(ctx.guild.id, False)
		await temp_config.clear_queue()
		temp_config.position = 0
		if ctx.voice_client is not None and ctx.voice_client.is_playing():
			ctx.voice_client.stop()
		await asyncio.sleep(1)
		await temp_config2.clear_queue()
		temp_config.position = 0
		async with MemcachedCache(serializer=Base64Serializer()) as cache:
			await cache.clear()
		embed = discord.Embed(title="Cache removed", description="Removed the audio cache.", color=0x00ff00)
		await ctx.respond(embed=embed, delete_after=30)

	@commands.slash_command(name="clean", description="Cleans the bot's messages", guild_ids=[761485410596552736])
	async def clean(self, ctx: discord.ApplicationContext,
					count: discord.Option(int, description="The number of messages to delete", required=False,
										  default=1)):  # type: ignore
		global removed_count
		await ctx.response.defer()
		if ctx.author.id != OWNER_ID:
			return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
		removed_count = 0

		def check(m: discord.Message):
			global removed_count
			removed_count += 1
			return m.author.id == self.bot.user.id and m.id != 1128641774789861488 and removed_count <= count

		await ctx.channel.purge(check=check)
		embed = discord.Embed(title="Clean", description=f"Cleaned {count} messages.", color=0x00ff00)
		await ctx.respond(embed=embed, delete_after=30)

	@commands.slash_command(name="reload", description="Reloads the cogs", guild_ids=[761485410596552736])
	async def reload(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.author.id != OWNER_ID:
			return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
		for cog in self.bot.cogs:
			self.bot.reload_extension(f"cogs.{cog}")
		embed = discord.Embed(title="Reload", description="Reloaded the cogs.", color=0x00ff00)
		await ctx.respond(embed=embed, delete_after=30)


def setup(bot):
	bot.add_cog(Admin(bot))
