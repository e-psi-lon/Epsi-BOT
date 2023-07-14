from discord.ext import commands
import discord
from utils import *


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="remove_cache", description="Removes the audio cache")
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
        for file in os.listdir('audio/'):
            os.remove(f'audio/{file}')
        embed = discord.Embed(title="Cache removed", description="Removed the audio cache.", color=0x00ff00)
        await ctx.respond(embed=embed, delete_after=30)


def setup(bot):
    bot.add_cog(Admin(bot))