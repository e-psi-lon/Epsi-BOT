from discord.commands import SlashCommandGroup
from utils.utils import *
import random


class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="queue", description="Shows the current queue")
    async def queue(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, True)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        embed = discord.Embed(title="Queue", color=0x00ff00)
        for i, song in enumerate(config.queue):
            if i == config.position:
                embed.add_field(name=f"{i + 1}. {song.name} - __**Now Playing**__",
                                value=f"{song.url} asked by <@{song.asker}>", inline=False)
            else:
                embed.add_field(name=f"{i + 1}. {song.name}", value=f"{song.url} asked by <@{song.asker}>",
                                inline=False)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="skip", description="Skips the current song")
    async def skip(self, ctx: discord.ApplicationContext,
                   by: discord.Option(int, "How many songs to skip", required=False)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if by is None:
            ctx.guild.voice_client.stop()
            return await ctx.respond(embed=discord.Embed(title="Skip", description="Song skipped.", color=0x00ff00))
        if by < 0 or by >= len(config.queue) or config.position + by >= len(config.queue):
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"Index {by} out of range.", color=0xff0000))
        config.position = config.position + by - 1
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Skip", description=f"Skipped {by} songs.", color=0x00ff00))

    loop = SlashCommandGroup(name="loop", description="Commands related to looping songs")

    @loop.command(name="song", description="Loops the current song")
    async def loop_song(self, ctx: discord.ApplicationContext,
                        state: discord.Option(bool, "The loop state", required=False)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if state is None:
            state = not config.loop_song
        config.loop_song = state
        if config.loop_queue and state:
            config.loop_queue = False
        await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop song set to {'on' if state else 'off'}.",
                                              color=0x00ff00))

    @loop.command(name="queue", description="Loops the current song")
    async def loop_queue(self, ctx: discord.ApplicationContext,
                         state: discord.Option(bool, "The loop state", required=False)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if state is None:
            state = not config.loop_queue
        config.loop_queue = state
        if config.loop_song and state:
            config.loop_song = False
        await ctx.respond(
            embed=discord.Embed(title="Loop", description=f"Loop queue set to {'on' if state else 'off'}.",
                                color=0x00ff00))

    @commands.slash_command(name="now", description="Shows the current song")
    async def now(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, True)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        song = config.queue[config.position]
        embed = discord.Embed(title="Now Playing",
                              description=f"[{song.name}]({song.url}) asked by <@{song.asker}>",
                              color=0x00ff00)
        await ctx.respond(embed=embed)

    remove = SlashCommandGroup(name="remove", description="Commands related to removing songs from the queue")

    @remove.command(name="from-name", description="Removes a song from the queue ")
    async def remove_name(self, ctx: discord.ApplicationContext,
                          song: discord.Option(str, "The name of the song to remove", required=True,
                                               autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        await config.remove_from_queue([songs for songs in config.queue if songs.name == song][0])
        await ctx.respond(
            embed=discord.Embed(title="Remove", description=f"Removed {song.name} from the queue.", color=0x00ff00))

    @remove.command(name="from-index", description="Removes a song from the queue ")
    async def remove_index(self, ctx: discord.ApplicationContext,
                           index: discord.Option(int, "The index of the song to remove", required=True)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if index < 0 or index >= len(config.queue):
            return await ctx.respond(embed=discord.Embed(title="Error", description=f"Index {index} out of range.",
                                                         color=0xff0000))
        song = config.queue[index-1]
        await config.remove_from_queue(song)
        await ctx.respond(
            embed=discord.Embed(title="Remove", description=f"Removed {song.name} from the queue.", color=0x00ff00))

    @commands.slash_command(name="clear", description="Clears the queue")
    async def clear(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        await config.clear_queue()
        config.position = 0
        if ctx.guild.voice_client is not None:
            try:
                ctx.guild.voice_client.stop()
            except discord.errors.ClientException:
                pass
        await ctx.respond(embed=discord.Embed(title="Clear", description="Queue cleared.", color=0x00ff00))

    @commands.slash_command(name="back", description="Goes back to the previous song")
    async def back(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if config.position == 0:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="There is no previous song.", color=0xff0000))
        config.position = config.position - 2
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Back", description="Playing previous song.", color=0x00ff00))

    @commands.slash_command(name="shuffle", description="Shuffles the queue")
    async def shuffle(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        temp_queue = config.queue.copy()
        random.shuffle(temp_queue)
        await config.edit_queue(temp_queue)
        await ctx.respond(embed=discord.Embed(title="Shuffle", description="Queue shuffled.", color=0x00ff00))

    random_command = SlashCommandGroup(name="random", description="Commands related to random mode")

    @random_command.command(name="toggle", description="Toggles the random mode")
    async def random_toggle(self, ctx: discord.ApplicationContext,
                            state: discord.Option(bool, "The random state", required=False)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if state is None:
            state = not config.random
        config.random = state
        await ctx.respond(
            embed=discord.Embed(title="Random", description=f"Random mode set to {'on' if state else 'off'}.",
                                color=0x00ff00))

    @random_command.command(name="query", description="Shows the current random state")
    async def random(self, ctx: discord.ApplicationContext):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, True)
        await ctx.respond(
            embed=discord.Embed(title="Random", description=f"Random mode is {'on' if config.random else 'off'}.",
                                color=0x00ff00))

    play = SlashCommandGroup(name="play-queue", description="Commands related to playing songs from the queue")

    @play.command(name="song", description="Plays a song from the queue")
    async def play_queue_song(self, ctx: discord.ApplicationContext,
                              song: discord.Option(str, "The index of the song to play", required=True,
                                                   autocomplete=discord.utils.basic_autocomplete(get_queue_songs))):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        index = get_index_from_title(song, config.queue)
        if index == -1:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"Song {song} not found in the queue.", color=0xff0000))
        config.position = index - 1
        ctx.guild.voice_client.stop()
        await ctx.respond(
            embed=discord.Embed(title="Play", description=f"Playing [{song}]({config.queue[index].url}).",
                                color=0x00ff00))

    @play.command(name="number", description="Plays a song from the queue")
    async def play_queue_index(self, ctx: discord.ApplicationContext,
                               index: discord.Option(int, "The index of the song to play", required=True)):
        await ctx.response.defer()
        config = await Config.get_config(ctx.guild.id, False)
        if not config.queue:
            return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
        if index < 0 or index > len(config.queue):
            return await ctx.respond(
                embed=discord.Embed(title="Error", description=f"Index {index} out of range.", color=0xff0000))
        config.position = index - 2
        ctx.guild.voice_client.stop()
        await ctx.respond(
            embed=discord.Embed(title="Play",
                                description=f"Playing [{config.queue[index - 1].title}]"
                                            f"({config.queue[index - 1].url}).",
                                color=0x00ff00))


def setup(bot):
    bot.add_cog(Queue(bot))
