import discord
from discord.ext import commands
import pytube
from utils import *
from classes import Research

class Others(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="download", description="Download the audio of a youtube video")
    # choices est une liste de formats audio uniquement (pas vidéo)
    async def download(self, ctx, query, format:discord.Option(str, description="The format of the file", choices=["mp3", "ogg"], required=False, default="ogg")):
        print(format)
        print(type(format))
        if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/'):
            await start_song(ctx, query)
        else:
            research = pytube.Search(query)
            results: list[pytube.YouTube] = research.results
            if len(results) == 0:
                await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND)
            elif len(results) == 1:
                file, video = download_audio(results[0].watch_url)
                if format != "ogg":
                    file = convert(file, format)
                embed = discord.Embed(title="Download", description=f"Downloaded song `{video.title}`", color=0x00ff00)
                await ctx.respond(embed=embed, file=discord.File(file))
            else:
                select = Research(results, ctx=ctx, download=True, format=format)
                embed = discord.Embed(title="Download", description="Select an audio to download", color=0x00ff00)
                await ctx.respond(embed=embed, view=select)


def setup(bot):
    bot.add_cog(Others(bot))