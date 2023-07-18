from discord.ext import commands
from discord.commands import SlashCommandGroup
from classes import *
from utils import *


class Queue(commands.Cog):
    @commands.slash_command(name="queue", description="Shows the current queue")
    async def queue(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        embed = discord.Embed(title="Queue", color=0x00ff00)
        for i, song in enumerate(queue['queue']):
            if i == queue['index']:
                embed.add_field(name=f"{i+1}. {song['title']} - **Now Playing**", value=f"song['url'] asked by {song['asker']}", inline=False)
            else:
                embed.add_field(name=f"{i+1}. {song['title']}", value=f"song['url'] asked by {song['asker']}", inline=False)
        await ctx.respond(embed=embed)


    @commands.slash_command(name="skip", description="Skips the current song")
    async def skip(self, ctx: discord.ApplicationContext,
                   by: discord.Option(int, "How many songs to skip", required=False)):
        pass

    loop = SlashCommandGroup(name="loop", description="Commands related to looping songs")

    @loop.command(name="song", description="Loops the current song")
    async def loop_song(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if state is None:
            state = not queue['loop_song']
        queue['loop_song'] = state
        if queue['loop_queue'] and state:
            queue['loop_queue'] = False
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop song set to {'on' if state else 'off'}.", color=0x00ff00))
        

    
    @loop.command(name="queue", description="Loops the current song")
    async def loop_queue(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if state is None:
            state = not queue['loop_queue']
        queue['loop_queue'] = state
        if queue['loop_song'] and state:
            queue['loop_song'] = False
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop queue set to {'on' if state else 'off'}.", color=0x00ff00))

    @commands.slash_command(name="now", description="Shows the current song")
    async def now(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx)
        if queue['queue'] == []:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        song = queue['queue'][queue['index']]
        embed = discord.Embed(title="Now Playing", description=f"[{song['title']}]({song['url']}) asked by {song['asker']}", color=0x00ff00)
        await ctx.respond(embed=embed)

    remove = SlashCommandGroup(name="remove", description="Commands related to removing songs from the queue")

    @remove.command(name="from-name", description="Removes a song from the queue ")
    async def remove_name(self, ctx: discord.ApplicationContext, song: discord.Option(str, "The name of the song to remove", required=True, autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        queue = get_queue(ctx.interaction.guild.id)
        index = get_index_from_title(queue, song)
        if index == -1:
            await ctx.respond(discord.Embed(title="Error", description=f"Song {song} not found in the queue.", color=0xff0000))
            return
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Remove", description=f"Removed {song} from the queue.", color=0x00ff00))


    @remove.command(name="from-index", description="Removes a song from the queue ")
    async def remove_index(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to remove", required=True)):
        queue = get_queue(ctx.interaction.guild.id)
        if index < 0 or index >= len(queue['queue']):
            await ctx.respond(discord.Embed(title="Error", description=f"Index {index} out of range.", color=0xff0000))
            return
        song = queue['queue'].pop(index)
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Remove", description=f"Removed {song['title']} from the queue.", color=0x00ff00))



    @commands.slash_command(name="clear", description="Clears the queue")
    async def clear(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        queue['queue'] = []
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Clear", description="Queue cleared.", color=0x00ff00))

    @commands.slash_command(name="back", description="Goes back to the previous song")
    async def back(self, ctx: discord.ApplicationContext):
        pass

    @commands.slash_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        random.shuffle(queue['queue'])
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Shuffle", description="Queue shuffled.", color=0x00ff00))

    random = SlashCommandGroup(name="random", description="Commands related to random mode")

    @random.command(name="toggle", description="Toggles the random mode")
    async def random_toggle(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The random state", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if state is None:
            state = not queue['random']
        queue['random'] = state
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Random", description=f"Random mode set to {'on' if state else 'off'}.", color=0x00ff00))

    @random.command(name="query", description="Shows the current random state")
    async def random(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        await ctx.respond(embed=discord.Embed(title="Random", description=f"Random mode is {'on' if queue['random'] else 'off'}.", color=0x00ff00))

    play = SlashCommandGroup(name="play-queue", description="Commands related to playing songs from the queue")

    @play.command(name="song", description="Plays a song from the queue")
    async def play_song(self, ctx: discord.ApplicationContext, song: discord.Option(str, "The index of the song to play", required=True, autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        pass

    @play.command(name="number", description="Plays a song from the queue")
    async def play_song(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to play", required=True)):
        pass

                          
        


def setup(bot):
    bot.add_cog(Queue(bot))
