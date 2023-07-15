from discord.ui.item import Item
from enum import Enum
from utils import *

class SelectVideo(discord.ui.Select):
    def __init__(self, videos: list[pytube.YouTube], ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.options = [
            discord.SelectOption(label=video.title, value=video.watch_url)
            for video in videos
        ]
    
    async def callback(self, interaction: discord.Interaction):
        queue = get_queue(self.ctx.guild.id)
        await interaction.response.defer()
        if self.view.download:
            file, video = download_audio(self.values[0])
            if file == -1:
                await interaction.message.edit(embed=EMBED_ERROR_VIDEO_TOO_LONG, view=None, remove_after=30)
                return
            if self.view.format != "ogg":
                file = convert(file, self.view.format)
            await interaction.message.edit(content=f'{video.title} downloaded', view=None, file=discord.File(file))
            return
        if self.view.playlist is not None:
            await interaction.message.edit(content=f"Add song `{self.options[0].label}` to the playlist `{self.view.playlist}`",
                                           view=None)
            queue['playlist'][self.view.playlist].append({'url': self.values[0], 'title': self.options[0].label, 'asker': interaction.user.id})
            update_queue(self.ctx.guild.id, queue)
        else:
            await start_song(self.ctx, self.values[0], message=interaction.message)


class Research(discord.ui.View):
    def __init__(self, videos, ctx, download: bool = False, file_format: str | None = None, playlist: str | None = None,
                 *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos=videos, ctx=ctx))
        self.playlist = playlist
        self.download = download
        self.format = file_format
