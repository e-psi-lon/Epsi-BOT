from discord.ext import commands
from utils import *
from classes import Research


class Others(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="download", description="Download the audio of a youtube video")
    # choices est une liste de formats audio uniquement (pas vidéo)
    async def download(self, ctx, query,
                       file_format: discord.Option(str, description="The file_format of the file", choices=["mp3", "ogg"],
                                                   required=False, default="ogg")):
        print(file_format)
        print(type(file_format))
        if query.startswith('https://www.youtube.com/watch?v=') or query.startswith('https://youtu.be/') or query.startswith('https://youtube.com/watch?v='):
            await start_song(ctx, query)
        else:
            research = pytube.Search(query)
            results: list[pytube.YouTube] = research.results
            if len(results) == 0:
                await ctx.respond(embed=EMBED_ERROR_NO_RESULTS_FOUND, delete_after=30)
            elif len(results) == 1:
                file, video = download_audio(results[0].watch_url)
                if file == -1:
                    await ctx.respond(embed=EMBED_ERROR_VIDEO_TOO_LONG, delete_after=30)
                    return
                if file_format != "ogg":
                    file = convert(file, file_format)
                embed = discord.Embed(title="Download", description=f"Downloaded song `{video.title}`", color=0x00ff00)
                await ctx.respond(embed=embed, file=discord.File(file))
            else:
                select = Research(results, ctx=ctx, download=True, file_format=file_format)
                embed = discord.Embed(title="Download", description="Select an audio to download", color=0x00ff00)
                await ctx.respond(embed=embed, view=select)

    @commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
    async def lyrics(self, ctx: discord.ApplicationContext):
        video = pytube.YouTube(get_queue(ctx.guild.id)['queue'][0]['url'])
        caption = [caption for caption in video.captions][0] if len(video.captions) > 0 else None
        if caption is None:
            embed = discord.Embed(title="Error", description="No lyrics found.", color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        embed = discord.Embed(title="Lyrics", description=caption, color=0x00ff00)
        await ctx.respond(embed=embed)
        return



def setup(bot):
    bot.add_cog(Others(bot))
