from discord.ext import commands
import discord
from utils import *


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="remove_cache", description="Removes the audio cache", guild_ids=[761485410596552736])
    async def remove_cache(self, ctx: discord.ApplicationContext):
        if ctx.author.id != OWNER_ID:
            embed = discord.Embed(title="Error", description="You are not the owner of the bot.", color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        if ctx.voice_client is not None:
            if ctx.voice_client.is_playing():
                embed = discord.Embed(title="Error", description="The bot is playing a song.", color=0xff0000)
                await ctx.respond(embed=embed, delete_after=30)
                return
        for file in os.listdir('cache/'):
            os.remove(f'cache/{file}')
        embed = discord.Embed(title="Cache removed", description="Removed the audio cache.", color=0x00ff00)
        await ctx.respond(embed=embed, delete_after=30)

    @commands.slash_command(name="clean", description="Cleans the bot's messages", guild_ids=[761485410596552736])
    async def clean(self, ctx: discord.ApplicationContext, count: discord.Option(int, description="The number of messages to delete", required=False, default=1)):
        if ctx.author.id != OWNER_ID:
            embed = discord.Embed(title="Error", description="You are not the owner of the bot.", color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        if ctx.channel.id != 761485410596552736:
            embed = discord.Embed(title="Error", description="You must be in <#761485410596552736> to use this command.", color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        await ctx.channel.purge(limit=count, check=lambda message: message.author.id == self.bot.user.id and message.id !=1128641774789861488)
        embed = discord.Embed(title="Clean", description=f"Cleaned {count} messages.", color=0x00ff00)
        await ctx.respond(embed=embed, delete_after=30)



def setup(bot):
    bot.add_cog(Admin(bot))