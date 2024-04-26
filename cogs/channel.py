import asyncio
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands

from utils import Config, EMBED_ERROR_BOT_NOT_CONNECTED, play_song, check_video


class Channel(commands.Cog):
    def __init__(self, bot: commands.Bot):
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
            futures = []
            if len(config.queue) > 1:
                with ThreadPoolExecutor() as pool:
                    for song in config.queue[:1]:
                        loop = asyncio.get_event_loop()
                        futures.append(loop.run_in_executor(pool, check_video, song.url, ctx))
                await asyncio.gather(*futures)



def setup(bot: commands.Bot):
    bot.add_cog(Channel(bot))
