from discord.ui.item import Item
from utils import *

class SelectVideo(discord.ui.Select):
    def __init__(self, videos:list[pytube.YouTube], ctx, download, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        self.ctx = ctx
        self.download = download
        self.options = [discord.SelectOption(label=video.title, value=video.title) for video in videos]
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.message.edit(embed=discord.Embed(title="Select audio", description=f"You selected : {self.values[0]}", color=0x00ff00), view=None)
        queue = get_queue(interaction.guild.id)
        if self.download:
            buffer = link_to_audio(self.values[0])
            if buffer is None:
                await interaction.message.edit(embed=discord.Embed(title="Error", description="Error while downloading song.", color=0xff0000))
                return
            await interaction.message.edit(embed=discord.Embed(title="Download", description="Song downloaded.", color=0x00ff00), file=discord.File(buffer, filename=f"{self.options[0].label}.mp3"), view=None)
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
            play_song(self.ctx, link_to_audio(queue['queue'][queue['index']]['url']))
        else:
            await interaction.message.edit(embed=discord.Embed(title="Queue", description=f"Song {self.values[0]} added to queue.", color=0x00ff00))

class Research(discord.ui.View):
    def __init__(self, videos:list[pytube.YouTube], ctx, download, *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)
        self.add_item(SelectVideo(videos, ctx, download))