import discord
from discord.ext import commands

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import OWNER_ID, EMBED_ERROR_NOT_BOT_OWNER, Server, AudioCache

removed_count = 0


def cogs_autocomplete(ctx: discord.AutocompleteContext):
	cogs = []
	for _, cog in ctx.bot.cogs.items():
		cogs.append(cog.qualified_name)
	cogs.append("all")
	return cogs


class Admin(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Bot administration commands"

	@commands.slash_command(name="remove_cache", description="Removes the audio cache", guild_ids=[761485410596552736])
	async def remove_cache(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		if ctx.author.id != OWNER_ID:
			return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
		server = await Server.get(server_id=ctx.guild.id)
		if ctx.voice_client is not None and ctx.voice_client.is_playing():
			ctx.voice_client.stop()
		await server.queue.all().delete()
		async with AudioCache(1) as cache:
			await cache.clear()
		embed = discord.Embed(title="Cache removed", description="Removed the audio cache.",
		                      color=discord.Color.green())
		await ctx.respond(embed=embed, delete_after=30)
		return None

	@commands.slash_command(name="clean", description="Cleans the bot's messages", guild_ids=[761485410596552736])
	@discord.option("count", int, description="The number of messages to delete", required=False, default=1,
	                min_value=1, max_value=100)
	async def clean(self, ctx: discord.ApplicationContext, count: int):
		global removed_count
		await ctx.response.defer()
		if ctx.author.id != OWNER_ID:
			return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
		removed_count = 0

		def check(m: discord.Message):
			global removed_count
			removed_count += 1
			return m.author.id == self.bot.user.id and m.id != 1128641774789861488 and removed_count <= count  # type: ignore[union-attr]

		await ctx.channel.purge(check=check)
		embed = discord.Embed(title="Clean", description=f"Cleaned {count} messages.", color=discord.Color.green())
		await ctx.respond(embed=embed, delete_after=30)
		return None

	@commands.slash_command(name="reload", description="Reloads the cogs", guild_ids=[761485410596552736])
	@discord.option("cog", str, description="The cog to reload", required=False, default="all",
	                autocomplete=discord.utils.basic_autocomplete(cogs_autocomplete))
	async def reload(self, ctx: discord.ApplicationContext, cog: str):
		if cog == "all":
			await ctx.response.defer()
			if ctx.author.id != OWNER_ID:
				return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
			for cog in self.bot.cogs:
				if cog == "admin":
					continue
				self.bot.reload_extension(f"epsi_bot.cogs.{cog}")
			embed = discord.Embed(title="Reload", description="Reloaded the cogs.", color=discord.Color.green())
			await ctx.respond(embed=embed, delete_after=30)
		else:
			await ctx.response.defer()
			if ctx.author.id != OWNER_ID:
				return await ctx.respond(embed=EMBED_ERROR_NOT_BOT_OWNER, delete_after=30)
			self.bot.reload_extension(f"epsi_bot.cogs.{cog}")
			embed = discord.Embed(title="Reload", description=f"Reloaded the {cog} cog.", color=discord.Color.green())
			await ctx.respond(embed=embed, delete_after=30)
		return None


def setup(bot):
	bot.add_cog(Admin(bot))
