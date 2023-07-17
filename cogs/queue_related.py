from discord.ext import commands
from discord.commands import SlashCommandGroup
from classes import *
from utils import *


class Queue(commands.Cog):
    @commands.slash_command(name="queue", description="Shows the current queue")
    async def queue(self, ctx: discord.ApplicationContext):
        pass

    @commands.slash_command(name="skip", description="Skips the current song")
    async def skip(self, ctx: discord.ApplicationContext,
                   by: discord.Option(int, "How many songs to skip", required=False)):
        pass

    loop = SlashCommandGroup(name="loop", description="Commands related to looping songs")

    @loop.command(name="song", description="Loops the current song")
    async def loop_song(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        pass
    
    @loop.command(name="queue", description="Loops the current song")
    async def loop_queue(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        pass

    @commands.slash_command(name="now", description="Shows the current song")
    async def now(self, ctx: discord.ApplicationContext):
        pass

    @commands.slash_command(name="remove", description="Removes a song from the queue ")
    async def remove(self, ctx: discord.ApplicationContext,
                     index: discord.Option(int, "The index of the song to remove", required=True)):
        pass

    @commands.slash_command(name="clear", description="Clears the queue")
    async def clear(self, ctx: discord.ApplicationContext):
        pass

    @commands.slash_command(name="back", description="Goes back to the previous song")
    async def back(self, ctx: discord.ApplicationContext):
        pass

    @commands.slash_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, ctx: discord.ApplicationContext):
       pass

    random = SlashCommandGroup(name="random", description="Commands related to random mode")

    @random.command(name="toggle", description="Toggles the random mode")
    async def random_toggle(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The random state", required=False)):
        pass

    @random.command(name="query", description="Shows the current random state")
    async def random(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The random state", required=False)):
        pass

    play = SlashCommandGroup(name="play-queue", description="Commands related to playing songs from the queue")

    @play.command(name="song", description="Plays a song from the queue")
    async def play_song(self, ctx: discord.ApplicationContext,
                          song: discord.Option(str, "The index of the song to play", required=True, autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        pass

    @play.command(name="number", description="Plays a song from the queue")
    async def play_song(self, ctx: discord.ApplicationContext,
                          index: discord.Option(int, "The index of the song to play", required=True)):
        pass

                          
        


def setup(bot):
    bot.add_cog(Queue(bot))
