from discord.ext import commands
from utils import *


class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, _: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):

        if after.channel is not None:
            if len(after.channel.members) == 1 and after.channel.members[0].id == self.bot.user.id:
                await disconnect_from_channel(after, self.bot)
        if before.channel is not None:
            if len(before.channel.members) == 1 and before.channel.members[0].id == self.bot.user.id:
                await disconnect_from_channel(before, self.bot)

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild: discord.Guild):
        create_queue(guild.id)
        channel = guild.system_channel
        if channel is not None:
            await channel.send(
                'Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de '
                'jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en '
                'test')
        else:
            await guild.text_channels[0].send(
                'Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de '
                'jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en '
                'test')


def setup(bot):
    bot.add_cog(Listeners(bot))
