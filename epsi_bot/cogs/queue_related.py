import random

import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands
from tortoise.exceptions import NoValuesFetched

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import Server, EMBED_ERROR_QUEUE_EMPTY, EMBED_ERROR_BOT_NOT_CONNECTED, get_queue_songs, \
	get_index_from_title, \
	Song, Queue as ModelQueue


class Queue(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Commands related to queue manipulation"

	@commands.slash_command(name="queue", description="Shows the current queue")
	async def queue(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if not await server.queue.all():
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		queue_len = 0
		try:
			queue_len = len(server.queue)
		except NoValuesFetched:
			pass
		embed = discord.Embed(title="Queue",
		                      description=f"- Current position: {server.position + 1} out of {queue_len}\n"
		                                  f"- Loop song: `{'on' if server.loop_song else 'off'}`\n"
		                                  f"- Loop queue: `{'on' if server.loop_queue else 'off'}`\n"
		                                  f"- Random: `{'on' if server.random else 'off'}`\n"
		                                  f"- Volume: {server.volume}",
		                      color=discord.Color.green())
		for i, queue_elem in enumerate(server.queue):
			song = await queue_elem.song
			await queue_elem.fetch_related("asker")
			if i == server.position:
				embed.add_field(name=f"{i + 1}. {song.name} - __**Now Playing**__",
				                value=f"{song.url} asked by <@{queue_elem.asker.discord_id}>", inline=False)
			else:
				embed.add_field(name=f"{i + 1}. {song.name}",
				                value=f"{song.url} asked by <@{queue_elem.asker.discord_id}>",
				                inline=False)
		await ctx.respond(embed=embed)

	@commands.slash_command(name="skip", description="Skips the current song")
	@discord.option("by", int, description="How many songs to skip", required=False)
	async def skip(self, ctx: discord.ApplicationContext, by: int):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
		loop_song = server.loop_song
		loop_queue = server.loop_queue
		server.loop_song = False
		server.loop_queue = False
		if not server.queue:
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		if ctx.guild.voice_client is None:
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if by is None:
			ctx.guild.voice_client.stop()
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(
				embed=discord.Embed(title="Skip", description="Song skipped.", color=discord.Color.green()))
		if by < 0 or by >= len(server.queue) or server.position + by >= len(server.queue):
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(
				embed=discord.Embed(title="Error", description=f"Index {by} out of range.",
				                    color=discord.Color.dark_red()))
		server.position = server.position + by - 1
		ctx.guild.voice_client.stop()
		server.loop_song = loop_song
		server.loop_queue = loop_queue
		await server.save()
		await ctx.respond(
			embed=discord.Embed(title="Skip", description=f"Skipped {by} songs.", color=discord.Color.green()))

	loop = SlashCommandGroup(name="loop", description="Commands related to looping songs")

	@loop.command(name="song", description="Loops the current song")
	@discord.option("state", bool, description="The loop state", required=False)
	async def loop_song(self, ctx: discord.ApplicationContext, state: bool):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if state is None:
			state = not server.loop_song
		server.loop_song = state
		if server.loop_queue and state:
			server.loop_queue = False
		await server.save()
		await ctx.respond(embed=discord.Embed(title="Loop", description=f"Loop song set to {'on' if state else 'off'}.",
		                                      color=discord.Color.green()))

	@loop.command(name="queue", description="Loops the current song")
	@discord.option("state", bool, description="The loop state", required=False)
	async def loop_queue(self, ctx: discord.ApplicationContext, state: bool):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if state is None:
			state = not server.loop_queue
		server.loop_queue = state
		if server.loop_song and state:
			server.loop_song = False
		await server.save()
		await ctx.respond(
			embed=discord.Embed(title="Loop", description=f"Loop queue set to {'on' if state else 'off'}.",
			                    color=discord.Color.green()))

	@commands.slash_command(name="now", description="Shows the current song")
	async def now(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song", "queue__asker")
		if not server.queue:
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		queue_elem = server.queue[server.position]
		song = queue_elem.song
		embed = discord.Embed(title="Now Playing",
		                      description=f"[{song.name}]({song.url}) asked by <@{queue_elem.asker.discord_id}>",
		                      color=discord.Color.green())
		await ctx.respond(embed=embed)

	remove = SlashCommandGroup(name="remove", description="Commands related to removing songs from the queue")

	@remove.command(name="from-name", description="Removes a song from the queue")
	@discord.option("song", str, description="The name of the song to remove", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_queue_songs))
	async def remove_name(self, ctx: discord.ApplicationContext, song: str):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if not await server.queue.all():
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		# Remove the song from the queue but using the ORM
		queue_elem = await ModelQueue.get(server=server, song=await Song.get(name=song))
		await queue_elem.delete()
		await ctx.respond(
			embed=discord.Embed(title="Remove", description=f"Removed {song} from the queue.",
			                    color=discord.Color.green()))

	@remove.command(name="from-index", description="Removes a song from the queue ")
	@discord.option("index", int, description="The index of the song to remove", required=True)
	async def remove_index(self, ctx: discord.ApplicationContext, index: int):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if index < 0 or index >= len(server.queue):
			return await ctx.respond(embed=discord.Embed(title="Error", description=f"Index {index} out of range.",
			                                             color=discord.Color.dark_red()))
		queue_elem = await ModelQueue.get(server=server, position=index)
		song = queue_elem.song
		await queue_elem.delete()
		await ctx.respond(
			embed=discord.Embed(title="Remove", description=f"Removed {song.name} from the queue.",
			                    color=discord.Color.green()))

	@commands.slash_command(name="clear", description="Clears the queue")
	async def clear(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if not await server.queue.all():
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		await server.queue.all().delete()
		server.position = 0
		await server.save()
		if ctx.guild.voice_client is not None:
			try:
				ctx.guild.voice_client.stop()
			except discord.errors.ClientException:
				pass
		await ctx.respond(embed=discord.Embed(title="Clear", description="Queue cleared.", color=discord.Color.green()))

	@commands.slash_command(name="back", description="Goes back to the previous song")
	async def back(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		loop_song = server.loop_song
		loop_queue = server.loop_queue
		server.loop_song = False
		server.loop_queue = False
		if not server.queue:
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		if ctx.guild.voice_client is None:
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if server.position == 0:
			server.loop_song = loop_song
			server.loop_queue = loop_queue
			await server.save()
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="There is no previous song.",
				                    color=discord.Color.dark_red()))
		server.position = server.position - 2
		ctx.guild.voice_client.stop()
		server.loop_song = loop_song
		server.loop_queue = loop_queue
		await server.save()
		await ctx.respond(
			embed=discord.Embed(title="Back", description="Playing previous song.", color=discord.Color.green()))

	@commands.slash_command(name="shuffle", description="Shuffles the queue")
	async def shuffle(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue")
		if not server.queue:
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		temp_queue = (await server.queue.all()).copy()
		random.shuffle(temp_queue)
		for i, queue_elem in enumerate(temp_queue):
			queue_elem.position = i
			await queue_elem.save()
		await ctx.respond(
			embed=discord.Embed(title="Shuffle", description="Queue shuffled.", color=discord.Color.green()))

	random_command = SlashCommandGroup(name="random", description="Commands related to random mode")

	@random_command.command(name="toggle", description="Toggles the random mode")
	@discord.option("state", bool, description="The random state", required=False)
	async def random_toggle(self, ctx: discord.ApplicationContext, state: bool):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		if state is None:
			state = not server.random
		server.random = state
		await server.save()
		await ctx.respond(
			embed=discord.Embed(title="Random", description=f"Random mode set to {'on' if state else 'off'}.",
			                    color=discord.Color.green()))

	@random_command.command(name="query", description="Shows the current random state")
	async def random(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id)
		await ctx.respond(
			embed=discord.Embed(title="Random", description=f"Random mode is {'on' if server.random else 'off'}.",
			                    color=discord.Color.green()))

	play = SlashCommandGroup(name="play-queue", description="Commands related to playing songs from the queue")

	@play.command(name="song", description="Plays a song from the queue")
	@discord.option("song", str, description="The song to play", required=True,
	                autocomplete=discord.utils.basic_autocomplete(get_queue_songs))
	async def play_queue_song(self, ctx: discord.ApplicationContext, song: str):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
		if not await server.queue.all():
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		index = get_index_from_title(song, [queue_elem.song for queue_elem in server.queue])
		if index == -1:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description=f"Song {song} not found in the queue.",
				                    color=discord.Color.dark_red()))
		server.position = index - 1
		await server.save()
		ctx.guild.voice_client.stop()
		await ctx.respond(
			embed=discord.Embed(title="Play", description=f"Playing [{song}]({server.queue[index].song.url}).",
			                    color=discord.Color.green()))

	@play.command(name="number", description="Plays a song from the queue")
	@discord.option("index", int, description="The index of the song to play", required=True)
	async def play_queue_index(self, ctx: discord.ApplicationContext, index: int):
		await ctx.response.defer()
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
		if not await server.queue.all():
			return await ctx.respond(embed=EMBED_ERROR_QUEUE_EMPTY)
		if index < 0 or index > len(server.queue):
			return await ctx.respond(
				embed=discord.Embed(title="Error", description=f"Index {index} out of range.",
				                    color=discord.Color.dark_red()))
		server.position = index - 2
		await server.save()
		ctx.guild.voice_client.stop()
		await ctx.respond(
			embed=discord.Embed(title="Play",
			                    description=f"Playing [{server.queue[index - 1].song.name}]"
			                                f"({server.queue[index - 1].song.url}).",
			                    color=discord.Color.green()))


def setup(bot: commands.Bot):
	bot.add_cog(Queue(bot))
