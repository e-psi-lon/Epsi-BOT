from discord.ext import commands
from utils import *


class Others(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="download", description="Download the audio of a youtube video")
    # choices est une liste de formats audio uniquement (pas vidéo)
    async def download(self, ctx, query, file_format: discord.Option(str, description="The file_format of the file", choices=["mp3", "ogg"], required=False, default="ogg")):
        try:
            video = pytube.YouTube(query)
            try:
                stream = video.streams.filter(only_audio=True).first()
                buffer = stream.stream_to_buffer()
                # On exporte le fichier dans un dossier cache
                with open(f"cache/{video.title}.{file_format}", "wb") as f:
                    f.write(buffer.read())
                # On convertit l'audio dans le format demandé
                buffer = open(convert("cache/" + video.title, file_format))
                await ctx.respond(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00), file=discord.File(f"cache/{video.title}.{file_format}", filename=f"{video.title}.{file_format}"))
                buffer.close()
                os.remove(f"cache/{video.title}.{file_format}")
                os.remove(f"cache/{video.title}.mp3")
            except:
                await ctx.respond(embed=discord.Embed(title="Error", description="Error while downloading song.", color=0xff0000))
                return
        except:
            videos = pytube.Search(query).results
            if videos == []:
                await ctx.respond(embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
                return
            view = Research(videos, ctx, True, timeout=60)
            await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to download", color=0x00ff00), view=view)
            



        
            

    @commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
    async def lyrics(self, ctx: discord.ApplicationContext):
        pass



def setup(bot):
    bot.add_cog(Others(bot))
