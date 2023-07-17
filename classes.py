from discord.ui.item import Item
from enum import Enum
from utils import *

class SelectVideo(discord.ui.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Select an audio to play"
        self.min_values = 1
        self.max_values = 1
        pass
    
    async def callback(self, interaction: discord.Interaction):
       pass


class Research(discord.ui.View):
    def __init__(self, *items: Item, timeout: float | None = 180, disable_on_timeout: bool = False):
        super().__init__(*items, timeout=timeout, disable_on_timeout=disable_on_timeout)