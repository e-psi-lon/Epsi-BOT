from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils import *


class Queue(commands.Cog):
    @commands.slash_command(name="queue", description="Shows the current queue")
    async def queue(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        embed = discord.Embed(title="Queue", color=0x00ff00)
        for i, song in enumerate(queue['queue']):
            if i == queue['index']:
                embed.add_field(name=f"{i+1}. {song['title']} - **Now Playing**", value=f"{song['url']} asked by <@{song['asker']}>", inline=False)
            else:
                embed.add_field(name=f"{i+1}. {song['title']}", value=f"{song['url']} asked by <@{song['asker']}>", inline=False)
        await ctx.respond(embed=embed)


    @commands.slash_command(name="skip", description="Skips the current song")
    async def skip(self, ctx: discord.ApplicationContext,
                   by: discord.Option(int, "How many songs to skip", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if by is None:
            ctx.guild.voice_client.stop()
            return await ctx.respond(embed=discord.Embed(title="Skip", description="Song skipped.", color=0x00ff00))
        if by < 0 or by >= len(queue['queue']) or queue['index'] + by >= len(queue['queue']):
            return await ctx.respond(embed=discord.Embed(title="Error", description=f"Index {by} out of range.", color=0xff0000))
        queue['index'] += by
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Skip", description=f"Skipped {by} songs.", color=0x00ff00))


    loop = SlashCommandGroup(name="loop", description="Commands related to looping songs")

    @loop.command(name="song", description="Loops the current song")
    async def loop_song(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if state is None:
            state = not queue['loop-song']
        queue['loop-song'] = state
        if queue['loop-queue'] and state:
            queue['loop-queue'] = False
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop song set to {'on' if state else 'off'}.", color=0x00ff00))
        

    
    @loop.command(name="queue", description="Loops the current song")
    async def loop_queue(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The loop state", required=False)):
        queue = get_queue(ctx.interaction.guild.id)
        if state is None:
            state = not queue['loop-queue']
        queue['loop-queue'] = state
        if queue['loop-song'] and state:
            queue['loop-song'] = False
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop queue set to {'on' if state else 'off'}.", color=0x00ff00))

    @commands.slash_command(name="now", description="Shows the current song")
    async def now(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        song = queue['queue'][queue['index']]
        embed = discord.Embed(title="Now Playing", description=f"[{song['title']}]({song['url']}) asked by <@{song['asker']}>", color=0x00ff00)
        await ctx.respond(embed=embed)

    remove = SlashCommandGroup(name="remove", description="Commands related to removing songs from the queue")

    @remove.command(name="from-name", description="Removes a song from the queue ")
    async def remove_name(self, ctx: discord.ApplicationContext, song: discord.Option(str, "The name of the song to remove", required=True, autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        queue = get_queue(ctx.interaction.guild.id)
        index = get_index_from_title(song, queue["queue"])
        if index == -1:
            return await ctx.respond(discord.Embed(title="Error", description=f"Song {song} not found in the queue.", color=0xff0000))
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Remove", description=f"Removed {song} from the queue.", color=0x00ff00))


    @remove.command(name="from-index", description="Removes a song from the queue ")
    async def remove_index(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to remove", required=True)):
        queue = get_queue(ctx.interaction.guild.id)
        if index < 0 or index >= len(queue['queue']):
            return await ctx.respond(discord.Embed(title="Error", description=f"Index {index} out of range.", color=0xff0000))
        song = queue['queue'].pop(index)
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Remove", description=f"Removed {song['title']} from the queue.", color=0x00ff00))



    @commands.slash_command(name="clear", description="Clears the queue")
    async def clear(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        queue['queue'] = []
        for file in os.listdir('cache/'):
            os.remove(f'cache/{file}')
        update_queue(ctx.interaction.guild.id, queue)
        await ctx.respond(embed=discord.Embed(title="Clear", description="Queue cleared.", color=0x00ff00))

    @commands.slash_command(name="back", description="Goes back to the previous song")
    async def back(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if queue['index'] == 0:
            return await ctx.respond(embed=discord.Embed(title="Error", description="There is no previous song.", color=0xff0000))
        queue['index'] -= 1
        update_queue(ctx.interaction.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Back", description="Playing previous song.", color=0x00ff00))

    @commands.slash_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
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
    async def play_queue_song(self, ctx: discord.ApplicationContext, song: discord.Option(str, "The index of the song to play", required=True, autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        index = get_index_from_title(song, queue['queue'])
        if index == -1:
            return await ctx.respond(discord.Embed(title="Error", description=f"Song {song} not found in the queue.", color=0xff0000))
        queue['index'] = index - 1
        update_queue(ctx.interaction.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Play", description=f"Playing {song}.", color=0x00ff00))

    @play.command(name="number", description="Plays a song from the queue")
    async def play_queue_index(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to play", required=True)):
        queue = get_queue(ctx.interaction.guild.id)
        if queue['queue'] == []:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if index < 0 or index >= len(queue['queue']):
            return await ctx.respond(discord.Embed(title="Error", description=f"Index {index} out of range.", color=0xff0000))
        queue['index'] = index - 2
        update_queue(ctx.interaction.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Play", description=f"Playing {queue['queue'][index]['title']}.", color=0x00ff00))

                          
        


def setup(bot):
    bot.add_cog(Queue(bot))
