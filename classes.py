from discord.ui.item import Item
from utils import *
import pytube
import discord


class PyTSource(discord.PCMVolumeTransformer):
    def __init__(self, source: discord.AudioSource, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url: str, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()

        # Utilise pytube pour obtenir les informations de la vidéo
        video = pytube.YouTube(url)

        data = {
            "title": video.title,
            "url": url
        }

        ffmpeg_options = {"options": "-vn"}
        return cls(discord.FFmpegPCMAudio(url, **ffmpeg_options), data=data)


class SelectVideo(discord.ui.Select):
    def __init__(self, videos:list[pytube.YouTube], ctx, download, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.download = download
        options = []
        for video in videos:
            if video in options:
                continue
            options.append(discord.SelectOption(label=video.title, value=video.watch_url))
        self.options = options
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.message.edit(embed=discord.Embed(title="Select audio", description=f"You selected : {self.values[0]}", color=0x00ff00), view=None)
        queue = get_queue(interaction.guild.id)
        if self.download:
            stream = pytube.YouTube(self.values[0]).streams.filter(only_audio=True).first()
            stream.download(filename=f"audio/{self.options[0].label}.mp3")
            await interaction.message.edit(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00), file=discord.File(f"audio/{self.options[0].label}", filename=f"{self.options[0].label}.mp3"), view=None)
            return
        if queue['queue'] == []:
            queue['index'] = 0
            queue['queue'].append({'title': self.values[0], 'url': self.values[0], 'asker': interaction.user.name})
            update_queue(interaction.guild.id, queue)
        else:
            queue['queue'].append({'title': self.values[0], 'url': self.values[0], 'asker': interaction.user.name})
            update_queue(interaction.guild.id, queue)
        if interaction.guild.voice_client is None:
            await interaction.user.voice.channel.connect()
        if not interaction.guild.voice_client.is_playing():
            await interaction.message.edit(embed=discord.Embed(title="Play", description=f"Playing {self.values[0]}", color=0x00ff00))
            play_song(self.ctx, queue['queue'][queue['index']]['url'])
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue", description=f"Song {self.values[0]} added to queue.", color=0x00ff00))

class Research(discord.ui.View):
    def __init__(self, videos:list[pytube.YouTube], ctx:discord.ApplicationContext, download: bool, *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos, ctx, download))