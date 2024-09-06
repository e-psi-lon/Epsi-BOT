import io
import contextlib
import sys
import traceback

import discord
from discord.ext import commands

from utils import disconnect_from_channel


class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def on_message(self, message:discord.Message):
        if message.content.startswith("e!eval"):
            output = io.StringIO()
            if message.author.id == self.bot.owner_id:
                try:
                    code = message.content.split("\n", 1)[1]
                    code = code[3:-3]
                    code = "\n".join(["\t" + line for line in code.split("\n")])
                    exec(f"async def __ex(message: discord.Message, bot: commands.Bot):\n{code}", globals(), locals())
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        with contextlib.redirect_stderr(output):
                            await locals()["__ex"](message, self.bot)
                except Exception:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    traceback_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                    output.write(f"Uncaught {exc_type.__name__}: {exc_value}\n{traceback_str}")
                finally:
                    await message.reply(f"```{output.getvalue()[:1994]}```", delete_after=10)
                

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(self, _: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):

        if after.channel is not None:
            if len(after.channel.members) == 1 and after.channel.members[0].id == self.bot.user.id:
                await disconnect_from_channel(after, self.bot)
                self.bot.logger.info("Bot disconnected from channel, no more members in it")
        if before.channel is not None:
            if len(before.channel.members) == 1 and before.channel.members[0].id == self.bot.user.id:
                await disconnect_from_channel(before, self.bot)
                self.bot.logger.info("Bot disconnected from channel, no more members in it")

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild: discord.Guild):
        channel = guild.system_channel
        text = 'Hey, je suis un bot de musique en cours de développement fait par ' \
               '<@!708006478807695450>, je permet de jouer de la musique depuis YouTube dans un channel ' \
               'vocal. Pour l\'instant, il est encore bugué donc en ' \
               'test'
        if channel is not None:
            try:
                await channel.send(text)
            except discord.Forbidden:
                try:
                    await guild.text_channels[0].send(text)
                except discord.Forbidden:
                    pass
        else:
            try:
                await guild.text_channels[0].send(text)
            except discord.Forbidden:
                pass


def setup(bot: commands.Bot):
    bot.add_cog(Listeners(bot))
