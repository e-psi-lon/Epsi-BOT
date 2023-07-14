from discord.ext import commands
from utils import *
from classes import Research


class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="play", description="Plays the audio of a YouTube video")
    async def play(self, ctx: discord.ApplicationContext, query: discord.Option(str, "The YouTube audio to play", required=True)):
        voice_client = ctx.voice_client
        await ctx.response.defer()
        if voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/'):
            await start_song(ctx, query)
        else:
            research = pytube.Search(query)
            results: list[pytube.YouTube] = research.results
            if len(results) == 0:
                await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND)
            elif len(results) == 1:
                await start_song(ctx, results[0].watch_url)
            else:
                select = Research(results, ctx=ctx)
                embed = discord.Embed(title="Select an audio to play", description="", color=0x00ff00)
                await ctx.respond(embed=embed, view=select)

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
            queue['index'] = 0
            queue['queue'] = []
            update_queue(ctx.guild.id, queue)
            embed = discord.Embed(title="Stop", description="Stopped the current song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_PLAYING)


def setup(bot):
    bot.add_cog(State(bot))
