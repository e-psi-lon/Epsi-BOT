import io

import discord
import pytubefix  # type: ignore[import-untyped]

from epsi_bot.utils.audio import get_youtube, play_song
from epsi_bot.utils.constants import EMBED_ERROR_BOT_NOT_CONNECTED, MAX_TRACK_LENGTH
from epsi_bot.utils.models import Queue, Server, Song, User, database_context


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
	select_type : discord.ComponentType
	        The type of the select menu (default: discord.ComponentType.string_select)
	custom_id : str | None
	        The custom ID of the select menu (default: None)
	placeholder : str | None
	        The placeholder text for the select menu (default: None)
	min_values : int
	        The minimum number of values that can be selected (default: 1)
	max_values : int
	        The maximum number of values that can be selected (default: 1)
	options : list[discord.SelectOption] | None
	        The options for the select menu (default: None)
	channel_types : list[discord.ChannelType] | None
	        The channel types for the select menu (default: None)
	disabled : bool
	        Whether the select menu is disabled or not (default: False)
	row : int | None
	        The row number of the select menu (default: None)
	"""

	def __init__(
		self,
		videos: list[pytubefix.YouTube],
		ctx: discord.ApplicationContext,
		download_file: bool,
		select_type: discord.ComponentType = discord.ComponentType.string_select,
		*,
		custom_id: str | None = None,
		placeholder: str | None = None,
		min_values: int = 1,
		max_values: int = 1,
		options: list[discord.SelectOption] | None = None,
		channel_types: list[discord.ChannelType] | None = None,
		disabled: bool = False,
		row: int | None = None,
	) -> None:
		if options is None:
			options = []
		if channel_types is None:
			channel_types = []

		super().__init__(
			select_type,
			custom_id=custom_id,
			placeholder=placeholder,
			min_values=min_values,
			max_values=max_values,
			options=options,
			channel_types=channel_types,
			disabled=disabled,
			row=row,
		)
		self.placeholder = "Select an audio to play"
		self.min_values = 1
		self.max_values = 1
		self.ctx = ctx
		self.download = download_file

		for video in videos:
			if any(option.value == video.watch_url for option in options):
				continue
			options.append(
				discord.SelectOption(label=video.title, value=video.watch_url)
			)
		self.options = options

	async def callback(self, interaction: discord.Interaction) -> None:
		"""
		Callback function to execute when a video is selected

		Parameters
		----------
		interaction : discord.Interaction
		        The interaction that triggered the callback
		"""
		if interaction.user is None or interaction.message is None:
			await interaction.response.send_message(
				"Error: Invalid interaction state.", ephemeral=True
			)
			return

		if interaction.user.id != self.ctx.author.id:
			await interaction.response.send_message(
				"You are not the author of the command.", ephemeral=True
			)
			return
		selected_url = str(self.values[0])
		await interaction.message.edit(
			embed=discord.Embed(
				title="Select audio",
				description=f"You selected : {self.options[0].label}",
				color=discord.Color.green(),
			),
			view=None,
		)

		if self.download:
			yt_video = get_youtube(selected_url)
			if yt_video.length > MAX_TRACK_LENGTH:
				await interaction.message.edit(
					embed=discord.Embed(
						title="Error",
						description=f"The video "
						f"[{yt_video.title}]({selected_url}) is too long",
						color=discord.Color.dark_red(),
					)
				)
				return
			stream = yt_video.streams.get_audio_only()
			buffer = io.BytesIO()
			stream.stream_to_buffer(buffer)
			buffer.seek(0)
			await interaction.message.edit(
				embed=discord.Embed(
					title="Download",
					description="Song downloaded.",
					color=discord.Color.green(),
				),
				file=discord.File(buffer, filename=f"{stream.title}.mp3"),
				view=None,
			)
			return

		if interaction.guild is None:
			await interaction.message.edit(
				embed=discord.Embed(
					title="Error",
					description="This command can only be used in a guild.",
					color=discord.Color.dark_red(),
				)
			)
			return

		async with database_context():
			server = await Server.get(server_id=interaction.guild.id).prefetch_related(
				"queue", "queue__song"
			)
			if not await server.queue.all():
				server.position = 0
				await server.save()
				yt_video = get_youtube(selected_url)
				song, _ = await Song.get_or_create_important(
					["url"], url=selected_url, name=yt_video.title
				)
				user, _ = await User.get_or_create(discord_id=interaction.user.id)
				await Queue.create(song=song, asker=user, position=0, server=server)
			else:
				yt_video = get_youtube(selected_url)
				song, _ = await Song.get_or_create_important(
					["url"], url=selected_url, name=yt_video.title
				)
				user, _ = await User.get_or_create(discord_id=interaction.user.id)
				await Queue.create(
					song=song, asker=user, position=len(server.queue), server=server
				)

			if interaction.guild.voice_client is None:
				await interaction.message.edit(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
				return

			if not interaction.guild.voice_client.is_playing():
				await interaction.message.edit(
					embed=discord.Embed(
						title="Play",
						description=f"Playing song "
						f"[{get_youtube(selected_url).title}]"
						f"({selected_url})",
						color=discord.Color.green(),
					)
				)
				await play_song(self.ctx, server.queue[server.position].song.url)
				return
			else:
				await interaction.message.edit(
					embed=discord.Embed(
						title="Queue",
						description=f"Song "
						f"[{get_youtube(selected_url).title}]"
						f"({selected_url}) added to queue.",
						color=discord.Color.green(),
					)
				)


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

	def __init__(
		self,
		videos: list[pytubefix.YouTube],
		ctx: discord.ApplicationContext,
		download_file: bool,
		*items: discord.ui.Item,
		timeout: float | None = 180,
		disable_on_timeout: bool = False,
	) -> None:
		super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
		self.add_item(SelectVideo(videos, ctx, download_file))
