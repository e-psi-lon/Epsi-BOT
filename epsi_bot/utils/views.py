import asyncio
import io

import discord
import pytubefix

from epsi_bot.utils.audio import get_youtube, play_song
from epsi_bot.utils.constants import EMBED_ERROR_BOT_NOT_CONNECTED, MAX_TRACK_LENGTH
from epsi_bot.utils.models import Queue, Server, Song, User


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
		*,
		custom_id: str | None = None,
		disabled: bool = False,
		row: int | None = None,
	) -> None:
		select_options: list[discord.SelectOption] = []
		seen: set[str] = set()
		for video in videos:
			if video.watch_url not in seen:
				seen.add(video.watch_url)
				select_options.append(
					discord.SelectOption(label=video.title, value=video.watch_url)
				)
		super().__init__(
			placeholder="Select an audio to play",
			custom_id=custom_id,
			options=select_options,
			disabled=disabled,
			row=row,
		)
		self.ctx = ctx
		self.download = download_file

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
		await interaction.response.edit_message(
			embed=discord.Embed(
				title="Select audio",
				description=f"You selected : {next(o.label for o in self.options if o.value == selected_url)}",
				color=discord.Color.green(),
			),
			view=None,
		)

		if self.download:
			yt_video = await asyncio.to_thread(get_youtube, selected_url)
			if yt_video.length > MAX_TRACK_LENGTH:
				await interaction.response.edit_message(
					embed=discord.Embed(
						title="Error",
						description=f"The video "
						f"[{yt_video.title}]({selected_url}) is too long",
						color=discord.Color.dark_red(),
					)
				)
				return
			stream = await asyncio.to_thread(yt_video.streams.get_audio_only)
			if not stream:
				await interaction.response.edit_message(
					embed=discord.Embed(
						title="Error",
						description=f"The video "
						f"[{yt_video.title}]({selected_url}) has no audio",
						color=discord.Color.dark_red(),
					)
				)
				return
			buffer = io.BytesIO()
			stream.stream_to_buffer(buffer)
			buffer.seek(0)
			await interaction.response.edit_message(
				embed=discord.Embed(
					title="Download",
					description="Song downloaded.",
					color=discord.Color.green(),
				),
				file=discord.File(buffer, filename=f"{stream.title}.mp3"),
				view=None,
			)
			return
		if (guild := interaction.guild) is None:
			await interaction.response.edit_message(
				embed=discord.Embed(
					title="Error",
					description="This command can only be used in a guild.",
					color=discord.Color.dark_red(),
				)
			)
			return
		server = await Server.get(server_id=guild.id).prefetch_related(
			"queue", "queue__song"
		)
		if not await server.queue.all():
			server.position = 0
			await server.save()
		yt_video = await asyncio.to_thread(get_youtube, selected_url)
		song, _ = await Song.get_or_create(
			url=selected_url, defaults={"name": yt_video.title}
		)
		user, _ = await User.get_or_create(user_id=interaction.user.id)
		_, created = await Queue.get_or_create(
			server=server, song=song, defaults={"asker": user}
		)
		if not created:
			await interaction.response.edit_message(
				embed=discord.Embed(
					title="Error",
					description="This song is already in the queue.",
					color=discord.Color.dark_red(),
				)
			)
			return

		if (voice_client := guild.voice_client) is None:
			await interaction.response.edit_message(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
			return

		if not voice_client.is_playing():
			await interaction.response.edit_message(
				embed=discord.Embed(
					title="Play",
					description=f"Playing song [{yt_video.title}]({selected_url})",
					color=discord.Color.green(),
				)
			)
			await play_song(self.ctx, server.queue[server.position].song.url)
			return
		else:
			await interaction.response.edit_message(
				embed=discord.Embed(
					title="Queue",
					description=f"Song "
					f"[{yt_video.title}]"
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
		*items: discord.ui.ViewItem[discord.ui.BaseView],
		timeout: float | None = 180,
		disable_on_timeout: bool = False,
	) -> None:
		super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
		self.add_item(SelectVideo(videos, ctx, download_file))
