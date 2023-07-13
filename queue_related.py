import discord
from discord.ext import commands
from utils import *
from classes import *

class Queue(commands.Cog):
    @commands.slash_command(name="queue", description="Shows the current queue")
    async def queue(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        embed = discord.Embed(title="Queue", description="The current queue", color=0x00ff00)
        for i, song in enumerate(queue['queue']):
            embed.add_field(name=f"**`{i+1}.`**{song['title']}", value=f"{song['url']} asked by <@{song['asker']}> {'- __**Currently playing**__' if i == queue['index'] else ''} ", inline=False)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="skip", description="Skips the current song")
    async def skip(self, ctx: discord.ApplicationContext, how_much: discord.Option(int, "How many songs to skip", required=False)):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        queue['loop-song'] = False
        update_queue(ctx.guild.id, queue)
        previous_random = queue['random']
        if queue['random']:
            # On le désactive temporairement
            queue['random'] = False
            update_queue(ctx.guild.id, queue)
        for _ in range(how_much if how_much is not None else 1):
            ctx.voice_client.stop()
        queue['random'] = previous_random
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Skip", description="Skipped the current song.", color=0x00ff00)
        await ctx.respond(embed=embed)


    @commands.slash_command(name="loop", description="Loops the current song")
    async def loop(self, ctx: discord.ApplicationContext, toloop: discord.Option(Loop, "The loop type", required=True), state: discord.Option(bool, "The loop state", required=False)):
        queue = get_queue(ctx.guild.id)
        if toloop == Loop.Song:
            if state is None:
                queue['loop-song'] = not queue['loop-song']
                queue['loop-queue'] = False if queue['loop-song'] else queue['loop-queue']
            else:
                queue['loop-song'] = state
                queue['loop-queue'] = False if queue['loop-song'] else queue['loop-queue']
            embed = discord.Embed(title="Loop", description=f"Looping around the current song is now {'enabled' if queue['loop-song'] else 'disabled'}{' and the queue is now not looped' if queue['loop-song'] else ''}.", color=0x00ff00)
            await ctx.respond(embed=embed)
        elif toloop == Loop.Queue:
            if state is None:
                queue['loop-queue'] = not queue['loop-queue']
                queue['loop-song'] = False if queue['loop-queue'] else queue['loop-song']
            else:
                queue['loop-queue'] = state
                queue['loop-song'] = False if queue['loop-queue'] else queue['loop-song']
            embed = discord.Embed(title="Loop", description=f"Looping around the queue is now {'enabled' if queue['loop-queue'] else 'disabled'}{' and the current song is now not looped' if queue['loop-queue'] else ''}.", color=0x00ff00)
            await ctx.respond(embed=embed)
        update_queue(ctx.guild.id, queue)


    @commands.slash_command(name="remove", description="Removes a song from the queue ")
    async def remove(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to remove", required=True)):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        if index > len(queue['queue']):
            await ctx.respond(embed=EMBED_ERROR_INDEX_TOO_HIGH)
            return
        song = queue['queue'].pop(index-1)
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Remove", description=f"Removed song `{song['title']}` from the queue.", color=0x00ff00)
        await ctx.respond(embed=embed)


    @commands.slash_command(name="clear", description="Clears the queue")
    async def clear(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Clear", description="Cleared the queue.", color=0x00ff00)
        await ctx.respond(embed=embed)
    
    @commands.slash_command(name="restart", description="Restarts the current song")
    async def restart(self, ctx: discord.ApplicationContext):
        if ctx.voice_client.is_playing():
            queue = get_queue(ctx.guild.id)
            queue['index'] -= 1
            update_queue(ctx.guild.id, queue)
            ctx.voice_client.stop()
            embed = discord.Embed(title="Restart", description="Restarted the current song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_PLAYING)
            return

    @commands.slash_command(name="back", description="Goes back to the previous song")
    async def back(self, ctx: discord.ApplicationContext):
        if ctx.voice_client.is_playing():
            queue = get_queue(ctx.guild.id)
            queue['index'] -= 2
            if queue['index'] < -1:
                embed = discord.Embed(title="Error", description="There is no previous song.", color=0xff0000)
                await ctx.respond(embed=embed)
                return
            update_queue(ctx.guild.id, queue)
            ctx.voice_client.stop()
            embed = discord.Embed(title="Back", description="Went back to the previous song.", color=0x00ff00)
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_PLAYING)
            return
    
    @commands.slash_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, ctx: discord.ApplicationContext):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        random.shuffle(queue['queue'])
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Shuffle", description="Shuffled the queue.", color=0x00ff00)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="random", description="Toggles the random mode")
    async def random(self, ctx: discord.ApplicationContext, state: discord.Option(bool, "The random state", required=False)):
        queue = get_queue(ctx.guild.id)
        if state is None:
            queue['random'] = not queue['random']
        else:
            queue['random'] = state
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Random", description=f"Random mode is now {'enabled' if queue['random'] else 'disabled'}.", color=0x00ff00)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="play-number", description="Plays a song from the queue")
    async def play_number(self, ctx: discord.ApplicationContext, index: discord.Option(int, "The index of the song to play", required=True)):
        queue = get_queue(ctx.guild.id)
        if len(queue['queue']) == 0:
            await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
            return
        if index > len(queue['queue']):
            await ctx.respond(embed=EMBED_ERROR_INDEX_TOO_HIGH)
            return
        previous_random = queue['random']
        if queue['random']:
            # On le désactive temporairement
            queue['random'] = False
            queue['index'] = 0
            update_queue(ctx.guild.id, queue)
        for _ in range(index-1):
            ctx.voice_client.stop()
        queue['random'] = previous_random
        update_queue(ctx.guild.id, queue)
        embed = discord.Embed(title="Play", description=f"Playing song `{queue['queue'][queue['index']]['title']}`.", color=0x00ff00)
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Queue(bot))