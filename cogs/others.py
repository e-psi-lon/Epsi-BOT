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
        pass

    @commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
    async def lyrics(self, ctx: discord.ApplicationContext):
        pass



def setup(bot):
    bot.add_cog(Others(bot))
