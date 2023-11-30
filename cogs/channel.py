import threading
from utils import *


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
        queue = await get_config(ctx.guild.id, False)
        await queue.edit_queue([])
        await queue.set_position(0)
        await queue.close()

    @commands.slash_command(name='join', description='Join the voice channel you are in.')
    async def join(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        if ctx.guild.voice_client is not None:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
                                                               "channel.", color=0xff0000))
        queue = await get_config(ctx.guild.id, False)
        if ctx.author.voice is None:
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
                                                         color=0xff0000))
        await ctx.author.voice.channel.connect()
        await ctx.respond(
            embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=0x00ff00))
        if queue.queue:
            if queue.position > len(queue.queue) - 1:
                await queue.set_position(0)
            await queue.close()
            # Si il y a plus d'un élément dans la queue on les télécharge tous sur un thread séparé
            await play_song(ctx, queue.queue[queue.position]['url'])
            if len(queue.queue) > 1:
                for song in queue.queue[1:]:
                    # On limite le nombre de threads à 3
                    while len([thread for thread in threading.enumerate() if thread.name.startswith("Download-")]) >= 3:
                        await asyncio.sleep(0.1)
                    video = pytube.YouTube(song['url'])
                    if video.length > 12000:
                        await ctx.respond(embed=discord.Embed(title="Error",
                                                              description=f"The video [{video.title}]({song['url']}) is too long",
                                                              color=0xff0000))
                    else:
                        threading.Thread(target=download, args=(song['url'],),
                                         name=f"Download-{video.video_id}").start()
        else:
            await queue.close()


def setup(bot):
    bot.add_cog(Channel(bot))
