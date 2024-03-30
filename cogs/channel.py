from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging

import discord
from discord.ext import commands
import pytube


from utils import Config, EMBED_ERROR_BOT_NOT_CONNECTED, Song, play_song, download


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
        config = await Config.get_config(ctx.guild.id, False)
        await config.edit_queue([])
        config.position = 0

    @commands.slash_command(name='join', description='Join the voice channel you are in.')
    async def join(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        if ctx.guild.voice_client is not None:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
                                                               "channel.", color=0xff0000))

        config = await Config.get_config(ctx.guild.id, False)
        if ctx.author.voice is None:
            return await ctx.respond(embed=discord.Embed(title="Error", description="You must be in a voice channel.",
                                                         color=0xff0000))

        await ctx.author.voice.channel.connect()
        await ctx.respond(
            embed=discord.Embed(title="Join", description="Bot joined the voice channel.", color=0x00ff00))
        if config.queue:
            if config.position > len(config.queue) - 1:
                config.position = 0

            await play_song(ctx, config.queue[config.position].url)
            if len(config.queue) > 1:
                pool = ThreadPoolExecutor()
                for song in config.queue[1:]:
                    pool.submit(self._check_video_length, song, ctx, asyncio.get_event_loop())
                pool.shutdown(False)

    @staticmethod
    def _check_video_length(song: Song, ctx: discord.ApplicationContext, error_loop: asyncio.AbstractEventLoop):
        try:
            if pytube.YouTube(song.url).length > 12000:
                asyncio.run_coroutine_threadsafe(
                    ctx.respond(embed=discord.Embed(title="Error",
                                                    description=f"The video [{pytube.YouTube(song.url).title}]"
                                                                f"({song.url}) is too long",
                                                    color=0xff0000)), error_loop)
            else:
                loop = asyncio.new_event_loop()
                asyncio.run_coroutine_threadsafe(download(song.url, download_logger=logging.getLogger("Audio-Downloader")), loop)
        except Exception as e:
            logging.error(f"Error checking video length: {e}")


def setup(bot):
    bot.add_cog(Channel(bot))
