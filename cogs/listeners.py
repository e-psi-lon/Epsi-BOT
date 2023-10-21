from discord.ext import commands
from utils import *


class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        print(before, after)
        if len(after.channel.members) == 0:
            ok = False
            for client in self.bot.voice_clients:
                for guild in client.client.guilds:
                    if guild.id == after.channel.guild.id:
                        await client.disconnect(force=True)
                        ok = True
                    if ok:
                        break
                if ok:
                    break

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild: discord.Guild):
        create_queue(guild.id)
        # Il faut envoyer un message dans le channel de bienvenue
        # On récupère le channel de bienvenue
        channel = guild.system_channel
        # On vérifie que le channel existe
        if channel is not None:
            # On envoie le message
            await channel.send(
                'Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de '
                'jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en '
                'test')
        else:
            # On envoie le message dans le premier channel textuel
            await guild.text_channels[0].send(
                'Hey, je suis un bot de musique en cours de développement fait par <@!708006478807695450>, il permet de '
                'jouer de la musique depuis YouTube dans un channel vocal. Pour l\'instant, il est encore bugué donc en '
                'test')


def setup(bot):
    bot.add_cog(Listeners(bot))
