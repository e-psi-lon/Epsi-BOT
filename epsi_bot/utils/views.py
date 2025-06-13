import io

import discord
import pytubefix

from epsi_bot.utils.audio import play_song, get_youtube
from epsi_bot.utils.constants import EMBED_ERROR_BOT_NOT_CONNECTED, MAX_TRACK_LENGTH
from epsi_bot.utils.models import User, Queue, Server, Song, database_context


class SelectVideo(discord.ui.Select):
	"""
	Select menu to select a video to play
	
	Parameters
	----------
	videos : list[pytubefix.YouTube]
		The list of videos to select from
	ctx : discord.ApplicationContext
		The context of the command
	download_file : bool
		Whether to download the file or not (useful for the download command)
	*args
		discord.ui.Select arguments
	**kwargs
		discord.ui.Select keyword arguments
	"""

	def __init__(self, videos: list[pytubefix.YouTube], ctx: discord.ApplicationContext, download_file: bool, *args,
	             **kwargs):
		super().__init__(*args, **kwargs)
		self.placeholder = "Select an audio to play"
		self.min_values = 1
		self.max_values = 1
		self.ctx = ctx
		self.download = download_file
		options: list[discord.SelectOption] = []
		for video in videos:
			if any(option.value == video.watch_url for option in options):
				continue
			options.append(discord.SelectOption(label=video.title, value=video.watch_url))
		self.options = options

	async def callback(self, interaction: discord.Interaction):
		"""
		Callback function to execute when a video is selected

		Parameters
		----------
		interaction : discord.Interaction
			The interaction that triggered the callback
		"""
		if interaction.user.id != self.ctx.author.id:
			return await interaction.response.send_message("You are not the author of the command.", ephemeral=True)
		await interaction.message.edit(
			embed=discord.Embed(title="Select audio", description=f"You selected : {self.options[0].label}",
			                    color=discord.Color.green()), view=None)
		if self.download:
			if get_youtube(self.values[0]).length > MAX_TRACK_LENGTH:
				return await interaction.message.edit(embed=discord.Embed(title="Error",
				                                                          description=f"The video "
				                                                                      f"""[{get_youtube(self.values[0])
				                                                          .title}]({self.values[0]}) is too long""",
				                                                          color=discord.Color.dark_red()))

			stream = get_youtube(self.values[0]).streams.get_audio_only()
			buffer = io.BytesIO()
			stream.stream_to_buffer(buffer)
			buffer.seek(0)
			return await interaction.message.edit(
				embed=discord.Embed(title="Download", description="Song downloaded.", color=discord.Color.green()),
				file=discord.File(buffer, filename=f"{stream.title}.mp3"),
				view=None)
		async with database_context():
			server = await Server.get(server_id=interaction.guild.id).prefetch_related("queue", "queue__song")
			if not await server.queue.all():
				server.position = 0
				await server.save()
				yt_video = get_youtube(self.values[0])
				song, _ = await Song.get_or_create_important(["url"], url=self.values[0], name=yt_video.title)
				user, _ = await User.get_or_create(discord_id=interaction.user.id)
				await Queue.create(song=song, asker=user, position=0, server=server)
			else:
				yt_video = get_youtube(self.values[0])
				song, _ = await Song.get_or_create_important(["url"], url=self.values[0], name=yt_video.title)
				user, _ = await User.get_or_create(discord_id=interaction.user.id)
				await Queue.create(song=song, asker=user, position=len(server.queue), server=server)
			if interaction.guild.voice_client is None:
				return await interaction.message.edit(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			if not interaction.guild.voice_client.is_playing():
				await interaction.message.edit(embed=discord.Embed(title="Play",
				                                                   description=f"Playing song "
				                                                               f"[{get_youtube(self.values[0]).title}]"
				                                                               f"({self.values[0]})",
				                                                   color=discord.Color.green()))
				await play_song(self.ctx, server.queue[server.position].song.url)
				return None
			else:
				await interaction.message.edit(embed=discord.Embed(title="Queue",
				                                                   description=f"Song "
				                                                               f"[{get_youtube(self.values[0]).title}]"
				                                                               f"({self.values[0]}) added to queue.",
				                                                   color=discord.Color.green()))
				return None


class Research(discord.ui.View):
	"""
	View to search for a video to play using a select menu

	Parameters
	----------
	videos : list[pytubefix.YouTube]
		The list of videos to select from
	ctx : discord.ApplicationContext
		The context of the command
	download_file : bool
		Whether to download the file or not (useful for the download command)
	*items
		discord.ui.View items
	timeout : float
		The timeout of the view
	disable_on_timeout : bool
		Whether to disable the view on timeout or not

	Methods
	-------
	callback(interaction: discord.Interaction)
		The callback function to execute when a video is selected
	"""

	def __init__(self, videos: list[pytubefix.YouTube], ctx: discord.ApplicationContext, download_file: bool, *items,
	             timeout: float | None = 180, disable_on_timeout: bool = False) -> None:
		super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
		self.add_item(SelectVideo(videos, ctx, download_file))
