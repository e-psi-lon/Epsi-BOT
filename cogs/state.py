import threading
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils import *
import pytube
import asyncio

class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="play", description="Plays the audio of a YouTube video")
    async def play(self, ctx: discord.ApplicationContext, query: discord.Option(str, "The YouTube audio to play", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        try:
            url = pytube.YouTube(query).watch_url
            try:
                queue = get_queue(ctx.guild.id)
                if queue['queue'] == []:
                    queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                    update_queue(ctx.guild.id, queue)
                    await ctx.respond(embed=discord.Embed(title="Play", description=f"Playing song [{pytube.YouTube(url).title}]({url})", color=0x00ff00))
                    await play_song(ctx, url)
                    return await asyncio.sleep(1)
                queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                update_queue(ctx.guild.id, queue)
                threading.Thread(target=download, args=(url,)).start()
                await ctx.respond(embed=discord.Embed(title="Queue", description=f"Song [{pytube.YouTube(url).title}]({url}) added to queue.", color=0x00ff00))
            except:
                return await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
        except:
            videos = pytube.Search(query).results
            if videos == []:
                return await ctx.respond(embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
            view = Research(videos, ctx, False)
            await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to play", color=0x00ff00), view=view)
    

    @commands.slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if ctx.guild.voice_client.is_paused():
            return await ctx.respond(embed=discord.Embed(title="Error", description="The song is already paused.", color=0xff0000))
        if not ctx.guild.voice_client.is_playing():
            return await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
        ctx.guild.voice_client.pause()
        await ctx.respond(embed=discord.Embed(title="Pause", description="Song paused.", color=0x00ff00))

    @commands.slash_command(name="resume", description="Resumes the current song")
    async def resume(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not ctx.guild.voice_client.is_paused():
            return await ctx.respond(embed=discord.Embed(title="Error", description="The song is not paused.", color=0xff0000))
        ctx.guild.voice_client.resume()
        await ctx.respond(embed=discord.Embed(title="Resume", description="Song resumed.", color=0x00ff00))

    @commands.slash_command(name="stop", description="Stops the current song")
    async def stop(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not ctx.guild.voice_client.is_playing():
            return await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
        queue = get_queue(ctx.guild.id)
        queue['index'] = 0
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Stop", description="Song stopped.", color=0x00ff00))

    volume = SlashCommandGroup(name="volume", description="Commands related to the volume of the bot")

    @volume.command(name="get", description="Gets the current volume")
    async def get_volume(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        try:
            await ctx.respond(embed=discord.Embed(title="Volume", description=f"Volume is {ctx.guild.voice_client.source.volume * 100}%", color=0x00ff00))
        except:
            await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting volume.", color=0xff0000))




def setup(bot):
    bot.add_cog(State(bot))
