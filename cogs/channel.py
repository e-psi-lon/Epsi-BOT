from discord.ext import commands
from classes import *
from utils import *



class Channel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="leave", description="Leaves the voice channel")
    async def leave(self, ctx: discord.ApplicationContext):
        if ctx.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED, delete_after=30)
            return
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        queue = json.load(open(f'queue/{ctx.guild.id}.json', 'r'))
        queue['index'] = 0
        queue['queue'] = []
        queue['channel'] = None
        with open(f'queue/{ctx.guild.id}.json', 'w') as f:
            json.dump(queue, f, indent=4)
        embed = discord.Embed(title="Leave", description="Left the voice channel.", color=0x00ff00)
        await ctx.respond(embed=embed)

    @commands.slash_command(name='join', description='Join the voice channel you are in.')
    async def join(self, ctx: discord.ApplicationContext):
        if ctx.voice_client is not None:
            embed = discord.Embed(title="Error", description="Bot is already connected to a voice channel.",
                                  color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        try:
            channel = ctx.author.voice.channel
            if not os.path.exists(f'queue/{ctx.guild.id}.json'):
                create_queue(ctx.guild.id)
        except AttributeError:
            embed = discord.Embed(title="Error", description="You are not in a voice channel.", color=0xff0000)
            await ctx.respond(embed=embed, delete_after=30)
            return
        embed = discord.Embed(title="Join", description=f"Joined the voice channel `{channel.name}`.", color=0x00ff00)
        await ctx.respond(embed=embed)
        await channel.connect()
        if len(get_queue(ctx.guild.id)['queue']) > 0:
            try:
                play_song(ctx, get_queue(ctx.guild.id)['queue'][0]['file'])
            except:
                file, _ = download_audio(get_queue(ctx.guild.id)['queue'][0]['url'])
                if file == -1:
                    ctx.message.reply(embed=EMBED_ERROR_VIDEO_TOO_LONG, delete_after=30)
                    return
                play_song(ctx, file)


def setup(bot):
    bot.add_cog(Channel(bot))
