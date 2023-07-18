from discord.ext import commands
from utils import *
from classes import Research


class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="play", description="Plays the audio of a YouTube video")
    async def play(self, ctx: discord.ApplicationContext, query: discord.Option(str, "The YouTube audio to play", required=True)):
        try:
            url = pytube.YouTube(query).watch_url
            try:
                buffer = link_to_audio(url)
                if buffer is None:
                    await ctx.respond(embed=discord.Embed(title="Error", description="Error while downloading song.", color=0xff0000))
                    return
                queue = get_queue(ctx.guild.id)
                if queue['queue'] == []:
                    queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                    update_queue(ctx.guild.id, queue)
                    play_song(ctx, buffer)
                    await asyncio.sleep(1)
                    return
                queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                update_queue(ctx.guild.id, queue)
                await ctx.respond(embed=discord.Embed(title="Success", description="Song added to queue.", color=0x00ff00))
            except:
                await ctx.respond(embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
                return
        except:
            videos = pytube.Search(query).results
            if videos == []:
                await ctx.respond(embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
                return
            view = Research(videos, ctx, False, "", timeout=60)
            await ctx.respond(embed=discord.Embed(title="Select audio", description="Select an audio to play", color=0x00ff00), view=view)
    

    @commands.slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if ctx.guild.voice_client.is_paused():
            await ctx.respond(embed=discord.Embed(title="Error", description="The song is already paused.", color=0xff0000))
            return
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
            return
        ctx.guild.voice_client.pause()
        await ctx.respond(embed=discord.Embed(title="Pause", description="Song paused.", color=0x00ff00))

        
        
        

    @commands.slash_command(name="resume", description="Resumes the current song")
    async def resume(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if not ctx.guild.voice_client.is_paused():
            await ctx.respond(embed=discord.Embed(title="Error", description="The song is not paused.", color=0xff0000))
            return
        ctx.guild.voice_client.resume()
        await ctx.respond(embed=discord.Embed(title="Resume", description="Song resumed.", color=0x00ff00))

    @commands.slash_command(name="stop", description="Stops the current song")
    async def stop(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
            return
        if not ctx.guild.voice_client.is_playing():
            await ctx.respond(embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
            return
        queue = get_queue(ctx.guild.id)
        queue['index'] = 0
        queue['queue'] = []
        update_queue(ctx.guild.id, queue)
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Stop", description="Song stopped.", color=0x00ff00))


def setup(bot):
    bot.add_cog(State(bot))
