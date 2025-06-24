import io

import discord
import pytubefix.exceptions  # type: ignore[import-untyped]
from discord.ext import commands

from epsi_bot.bot.bot import Bot
from epsi_bot.utils import Server, EMBED_ERROR_BOT_NOT_CONNECTED, convert, Research, get_lyrics, FfmpegFormats, \
	get_youtube, YOUTUBE_CLIENT, YOUTUBE_REGEX


class Others(commands.Cog):
	def __init__(self, bot: Bot) -> None:
		self.bot = bot
		self.description = "Other commands"

	@commands.slash_command(name="download_file", description="Download the audio of a youtube video")
	@discord.option("file-format", str, description="The file_format of the file", choices=["mp3", "ogg"],
	                required=False, default="ogg", parameter_name="file_format", min_length=3, max_length=3)
	async def download_file(self, ctx: discord.ApplicationContext, query: str, file_format: str) -> None:
		await ctx.response.defer()
		try:
			video = get_youtube(query)
			try:
				stream = video.streams.get_audio_only()
				buffer = io.BytesIO()
				stream.stream_to_buffer(buffer)
				buffer.seek(0)
				# Don't ask why the code is unreachable, because it literally is reachable, but PyCharm doesn't
				# understand that
				# noinspection PyUnreachableCode
				match file_format:
					case "mp3":
						buffer = await convert(buffer, FfmpegFormats.MP3)
					case "ogg":
						buffer = await convert(buffer, FfmpegFormats.OGG)
					case _:
						await ctx.respond(
							embed=discord.Embed(title="Error", description="Invalid file_format.",
							                    color=discord.Color.dark_red())
						)
						return
				await ctx.respond(
					embed=discord.Embed(title="Download", description="Song downloaded.", color=discord.Color.green()),
					file=discord.File(buffer,
					                  filename=f"{video.title}.{file_format}"))
			except pytubefix.exceptions.PytubeFixError:
				await ctx.respond(
					embed=discord.Embed(title="Error", description="Error while downloading song.",
					                    color=discord.Color.dark_red()))
				return
		except pytubefix.exceptions.RegexMatchError:
			videos = pytubefix.Search(query, client=YOUTUBE_CLIENT).results
			if not videos:
				await ctx.respond(
					embed=discord.Embed(title="Error", description="No results found.", color=discord.Color.dark_red()))
				return
			view = Research(videos, ctx, True, timeout=60)
			await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to download.",
			                                      color=discord.Color.green()), view=view)

	@commands.slash_command(name="lyrics", description="Shows the lyrics of the current song")
	async def lyrics(self, ctx: discord.ApplicationContext) -> None:
		await ctx.response.defer()
		if ctx.guild.voice_client is None:
			await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return
		server = await Server.get(server_id=ctx.guild.id).prefetch_related("queue", "queue__song")
		if not await server.queue.all():
			await ctx.respond(
				embed=discord.Embed(title="Error", description="No song is currently playing.",
				                    color=discord.Color.dark_red()))
		elif not YOUTUBE_REGEX.match(server.queue[server.position].song.url):
			await ctx.respond(
				embed=discord.Embed(title="Error", description="This command is only available for youtube videos.",
				                    color=discord.Color.dark_red()))
			return
		video = get_youtube(server.queue[server.position].song.url)
		lyrics = get_lyrics(video.title)
		if not lyrics:
			await ctx.respond(
				embed=discord.Embed(title="Error", description="No lyrics found.", color=discord.Color.dark_red()))
		else:
			await ctx.respond(embed=discord.Embed(title="Lyrics", description=lyrics, color=discord.Color.green()))


def setup(bot: Bot) -> None:
	bot.add_cog(Others(bot))
