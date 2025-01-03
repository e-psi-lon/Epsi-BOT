import io

import discord
import pytubefix.exceptions
from discord.ext import commands

from bot.bot import Bot
from utils import Server, EMBED_ERROR_BOT_NOT_CONNECTED, convert, Research, get_lyrics, FfmpegFormats


class Others(commands.Cog):
	def __init__(self, bot: Bot):
		self.bot = bot
		self.description = "Other commands"

	@commands.slash_command(name="download_file", description="Download the audio of a youtube video")
	async def download_file(self, ctx: discord.ApplicationContext, query,
					   file_format: discord.Option(str, description="The file_format of the file",
												   choices=["mp3", "ogg"], required=False,
												   default="ogg")):  # type: ignore
		await ctx.response.defer()
		try:
			video = pytubefix.YouTube(query)
			try:
				stream = video.streams.filter(only_audio=True).first()
				buffer = io.BytesIO()
				stream.stream_to_buffer(buffer)
				buffer.seek(0)
				# On convertit l'audio dans le format demandé
				match file_format:
					case "mp3":
						buffer = await convert(buffer, FfmpegFormats.MP3)
					case "ogg":
						buffer = await convert(buffer, FfmpegFormats.OGG)
					case _:
						return await ctx.respond(
							embed=discord.Embed(title="Error", description="Invalid file_format.", color=0xff0000)
						)
				await ctx.respond(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00),
								  file=discord.File(buffer,
													filename=f"{video.title}.{file_format}"))
			except pytubefix.exceptions.PytubeFixError:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="Error while downloading song.", color=0xff0000))
		except pytubefix.exceptions.RegexMatchError:
			videos = pytubefix.Search(query).results
			if not videos:
				return await ctx.respond(
					embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
			view = Research(videos, ctx, True, timeout=60)
			await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to download.",
												  color=0x00ff00), view=view)

	@commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
	async def lyrics(self, ctx: discord.ApplicationContext):
		await ctx.response.defer()
		server = Server.get(server_id=ctx.guild.id)
		if ctx.guild.voice_client is None:
			return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
		if not server.queue:
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="No song is currently playing.", color=0xff0000))
		if not server.queue[server.position].song.url.startswith("https://www.youtube.com/watch?v="):
			return await ctx.respond(
				embed=discord.Embed(title="Error", description="This command is only available for youtube videos.",
									color=0xff0000))
		video = pytubefix.YouTube(server.queue[server.position].song.url)
		lyrics = get_lyrics(video.title)
		if not lyrics:
			return await ctx.respond(embed=discord.Embed(title="Error", description="No lyrics found.", color=0xff0000))
		await ctx.respond(embed=discord.Embed(title="Lyrics", description=lyrics, color=0x00ff00))


def setup(bot: commands.Bot):
	bot.add_cog(Others(bot))
