from discord.ext import commands
from utils import *
from classes import Research


class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="play", description="Plays the audio of a YouTube video")
    async def play(self, ctx: discord.ApplicationContext, query: discord.Option(str, "The YouTube audio to play", required=True)):
        pass

    @commands.slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if ctx.guild.voice_client.is_paused():
            await ctx.respond(embed=discord.Embed(title="Error", description="The song is already paused.", color=0xff0000))
            return
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
            return
        ctx.guild.voice_client.pause()
        await ctx.respond(embed=discord.Embed(title="Pause", description="Song paused.", color=0x00ff00))

        
        
        

    @commands.slash_command(name="resume", description="Resumes the current song")
    async def resume(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if not ctx.guild.voice_client.is_paused():
            await ctx.respond(embed=discord.Embed(title="Error", description="The song is not paused.", color=0xff0000))
            return
        ctx.guild.voice_client.resume()
        await ctx.respond(embed=discord.Embed(title="Resume", description="Song resumed.", color=0x00ff00))

    @commands.slash_command(name="stop", description="Stops the current song")
    async def stop(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
            return
        queue = get_queue(ctx.guild.id)
        queue['index'] = 0
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Stop", description="Song stopped.", color=0x00ff00))


def setup(bot):
    bot.add_cog(State(bot))
