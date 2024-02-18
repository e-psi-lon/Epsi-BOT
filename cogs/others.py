from utils.utils import *
import pytube


class Others(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="download_file", description="Download the audio of a youtube video")
    # choices est une liste de formats audio uniquement (pas vidéo)
    async def download(self, ctx, query, file_format: discord.Option(str, description="The file_format of the file",
                                                                     choices=["mp3", "ogg"], required=False,
                                                                     default="ogg")):
        await ctx.response.defer()
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
                await ctx.respond(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
                                  file=discord.File(f"cache/{video.title}.{file_format}",
                                                    filename=f"{video.title}.{file_format}"))
                buffer.close()
                os.remove(f"cache/{video.title}.{file_format}")
                os.remove(f"cache/{video.title}.mp3")
            except:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="Error while downloading song.", color=0xff0000))
        except:
            videos = pytube.Search(query).results
            if not videos:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
            view = Research(videos, ctx, True, timeout=60)
            await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to download_file",
                                                  color=0x00ff00), view=view)

    @commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
    async def lyrics(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        queue = await Config.get_config(ctx.guild.id, True)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not queue.queue:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="No song is currently playing.", color=0xff0000))
        if not queue.queue[queue.position].url.startswith("https://www.youtube.com/watch?v="):
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="This command is only available for youtube videos.",
                                    color=0xff0000))
        video = pytube.YouTube(queue.queue[queue.position].url)
        lyrics = get_lyrics(video.title)
        if not lyrics:
            return await ctx.respond(embed=discord.Embed(title="Error", description="No lyrics found.", color=0xff0000))
        await ctx.respond(embed=discord.Embed(title="Lyrics", description=lyrics, color=0x00ff00))


def setup(bot):
    bot.add_cog(Others(bot))
