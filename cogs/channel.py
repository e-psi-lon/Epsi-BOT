import multiprocessing
import sys
from utils.utils import *


class Channel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="leave", description="Leaves the voice channel")
    async def leave(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        await ctx.guild.voice_client.disconnect(force=True)
        await ctx.respond(embed=discord.Embed(title="Leave", description="Bot left the voice channel.",
                                              color=0x00ff00))
        queue = await Config.get_config(ctx.guild.id, False)
        await queue.edit_queue([])
        queue.position = 0

    @commands.slash_command(name='join', description='Join the voice channel you are in.')
    async def join(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        if ctx.guild.voice_client is not None:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
                                                               "channel.", color=0xff0000))
        queue = await Config.get_config(ctx.guild.id, False)
        if ctx.author.voice is None:
            return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
                                                         color=0xff0000))
        await ctx.author.voice.channel.connect()
        await ctx.respond(
            embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=0x00ff00))
        if queue.queue:
            if queue.position > len(queue.queue) - 1:
                queue.position = 0
            # Si il y a plus d'un élément dans la queue on les télécharge tous sur un thread séparé
            await play_song(ctx, queue.queue[queue.position].url)
            if len(queue.queue) > 1:
                q = multiprocessing.Queue()
                p = multiprocessing.Process(target=worker, args=(q,), name="Audio-Downloader")
                p.start()
                for song in queue.queue[1:]:
                    if pytube.YouTube(song.url).length > 12000:
                        await ctx.respond(embed=discord.Embed(title="Error",
                                                              description=f"The video "
                                                                          f"[{pytube.YouTube(song.url).title}]"
                                                                          f"({song.url}) is too long",
                                                              color=0xff0000))
                    else:
                        q.put(song.url)
                q.put(None)
                p.join()


def worker(q: multiprocessing.Queue):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter(source="Audio-Downloader"))
    logging.basicConfig(level=logging.INFO, handlers=[console_handler])
    while True:
        url = q.get()
        if url is None:
            break
        download(url)
    q.close()


def setup(bot):
    bot.add_cog(Channel(bot))
