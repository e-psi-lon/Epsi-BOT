import discord
from discord.ui.item import Item
import pytube
from enum import Enum
from utils import *


class Loop(Enum):
    Song = 1
    Queue = 2


class SelectVideo(discord.ui.Select):
    def __init__(self, videos: list[pytube.YouTube], ctx, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.view: Research | None
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
            if self.view.format != "ogg":
                    file = convert(file, self.format)
            await self.ctx.respond(f'{video.title} downloaded', file=discord.File(file))
            return
        if self.view.playlist is not None:
            await interaction.message.edit(content=f"Add song `{self.values[0]}` to playlist `{self.playlist}`", view=None)
            queue['playlist'][self.playlist].append(self.values[0])
            update_queue(self.ctx.guild.id, queue)
        else:
            await start_song(self.ctx, self.values[0])


class Research(discord.ui.View):
    def __init__(self, videos, ctx, download: bool = False, format:str | None = None, playlist: str | None = None, *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos=videos, ctx=ctx))
        self.playlist = playlist
        self.download = download
        self.format = format
