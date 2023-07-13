from discord.ext import commands
import discord
from utils import *

class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if voice_client.is_playing():
            voice_client.pause()
            embed = discord.Embed(title="Pause", description="Paused the current song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_PLAYING)

    @commands.slash_command(name="resume", description="Resumes the current song")
    async def resume(self, ctx: discord.ApplicationContext):
        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if voice_client.is_paused():
            voice_client.resume()
            embed = discord.Embed(title="Resume", description="Resumed the current song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="Bot is not paused.", color=0xff0000)
            await ctx.respond(embed=embed)

    @commands.slash_command(name="stop", description="Stops the current song")
    async def stop(self, ctx: discord.ApplicationContext):
        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if voice_client.is_playing():
            voice_client.stop()
            queue = get_queue(ctx.guild.id)
            queue['queue'] = []
            update_queue(ctx.guild.id, queue)
            embed = discord.Embed(title="Stop", description="Stopped the current song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_PLAYING)




def setup(bot):
    bot.add_cog(State(bot))
