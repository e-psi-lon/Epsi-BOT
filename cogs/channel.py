from discord.ext import commands
from classes import *
from utils import *



class Channel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="leave", description="Leaves the voice channel")
    async def leave(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        await ctx.guild.voice_client.disconnect()
        await ctx.respond(embed=discord.Embed(title="Success", description="Bot left the voice channel.",
                                                color=0x00ff00))
        queue = get_queue(ctx.guild.id)
        queue['queue'] = []
        queue['index'] = 0
        update_queue(ctx.guild.id, queue)


    @commands.slash_command(name='join', description='Join the voice channel you are in.')
    async def join(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is not None:
            await ctx.respond(embed=discord.Embed(title="Error", description="Bot is already connected to a voice "
                                                                             "channel.", color=0xff0000))
            return
        queue = get_queue(ctx.guild.id)
        await ctx.author.voice.channel.connect()
        await ctx.respond(embed=discord.Embed(title="Success", description="Bot joined the voice channel.",
                                                color=0x00ff00))
        if queue['queue'] != []:
            play_song(ctx.guild.id, link_to_audio(queue['queue'][queue['index']]['url']))
            


def setup(bot):
    bot.add_cog(Channel(bot))
