import threading
from datetime import datetime
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils import *
import pytube
import asyncio

connections = {}


class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    play = SlashCommandGroup(name="play", description="Commands related to the audio of the bot")

    @play.command(name="url", description="Plays the audio of a file from an URL")
    async def play_url(self, ctx: discord.ApplicationContext,
                       url: discord.Option(str, "The URL of the audio to play", required=True)):
        if ctx.user.id in [501303816302362635, 942531230291877910]:
            return await ctx.respond(embed=discord.Embed(title="Error", description="Non mais tu me prends pour qui, je te connais hein",
                                                         color=0xff0000))
        if url.startswith("https://www.youtube.com/") or url.startswith("https://youtu.be/") or url.startswith("https://youtube.com/"):
            return await self.play_youtube(ctx, url)
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not url.startswith("http"):
            return await ctx.respond(embed=discord.Embed(title="Error", description="Invalid URL.", color=0xff0000))
        if url.split('/')[-1].split('.')[-1].split("?")[0] not in ['mp3', 'wav', 'ogg', 'mp4']:
            return await ctx.respond(embed=discord.Embed(title="Error", description="Invalid URL.", color=0xff0000))
        queue = await get_config(ctx.guild.id, False)
        if not queue.queue:
            await queue.add_song_to_queue({'title': url.split('/')[-1].split('?')[0], 'url': url, 'asker': ctx.author.id})
            await ctx.respond(embed=discord.Embed(title="Play",
                                                  description=f"Playing song [{url.split('/')[-1].split('?')[0]}]({url})",
                                                  color=0x00ff00))
            await play_song(ctx, url)
            await queue.close()
            return await asyncio.sleep(1)
        await queue.add_song_to_queue({'title': url.split('/')[-1].split('?')[0], 'url': url, 'asker': ctx.author.id})
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Queue",
                                              description=f"Song [{url.split('/')[-1].split('?')[0]}]({url}) added to queue.",
                                              color=0x00ff00))

    @play.command(name="file", description="Plays the audio of a file")
    async def play_file(self, ctx: discord.ApplicationContext,
                        file: discord.Option(discord.Attachment, "The file to play", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if file.content_type not in ['audio/mpeg', 'audio/wav', 'audio/ogg', 'video/mp4']:
            return await ctx.respond(embed=discord.Embed(title="Error", description="File is not an audio file.",
                                                         color=0xff0000))
        if file.size > 10000000:
            return await ctx.respond(embed=discord.Embed(title="Error", description="File is too big.", color=0xff0000))
        url = file.url
        queue = await get_config(ctx.guild.id, False)
        if not queue.queue:
            await queue.add_song_to_queue({'title': file.filename, 'url': url, 'asker': ctx.author.id})
            await queue.close()
            await ctx.respond(embed=discord.Embed(title="Play",
                                                  description=f"Playing song [{file.filename}]({url})",
                                                  color=0x00ff00))
            await play_song(ctx, url)
            return await asyncio.sleep(1)
        await queue.add_song_to_queue({'title': file.filename, 'url': url, 'asker': ctx.author.id})
        await queue.close()
        await ctx.respond(embed=discord.Embed(title="Queue",
                                              description=f"Song [{file.filename}]({url}) added to queue.",
                                              color=0x00ff00))

    @play.command(name="youtube", description="Plays the audio of a YouTube video")
    async def play_youtube(self, ctx: discord.ApplicationContext,
                   query: discord.Option(str, "The YouTube audio to play", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        try:
            url = pytube.YouTube(query).watch_url
            try:
                queue = await get_config(ctx.guild.id, False)
                if not queue.queue:
                    await queue.add_song_to_queue({'title': pytube.YouTube(query).title, 'url': url, 'asker': ctx.author.id})
                    await queue.close()
                    await ctx.respond(embed=discord.Embed(title="Play",
                                                          description=f"Playing song [{pytube.YouTube(url).title}]({url})",
                                                          color=0x00ff00))
                    await play_song(ctx, url)
                    return await asyncio.sleep(1)
                await queue.add_song_to_queue({'title': pytube.YouTube(query).title, 'url': url, 'asker': ctx.author.id})
                await queue.close()
                video = pytube.YouTube(url)
                if video.length > 12000:
                    return await ctx.respond(
                        discord.Embed(title="Error", description=f"The video [{video.title}]({url}) is too long",
                                      color=0xff0000))
                threading.Thread(target=download, args=(url,), name=f"Download-{video.video_id}").start()
                await ctx.respond(embed=discord.Embed(title="Queue",
                                                      description=f"Song [{pytube.YouTube(url).title}]({url}) added to queue.",
                                                      color=0x00ff00))
            except:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="Error while getting song.", color=0xff0000))
        except:
            videos = pytube.Search(query).results
            if not videos:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="No results found.", color=0xff0000))
            view = Research(videos, ctx, False)
            await ctx.respond(
                embed=discord.Embed(title="Select audio", description=f"Select an audio to play for query `{query}` from the list below",
                                    color=0x00ff00), view=view)

    @commands.slash_command(name="pause", description="Pauses the current song")
    async def pause(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if ctx.guild.voice_client.is_paused():
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="The song is already paused.", color=0xff0000))
        if not ctx.guild.voice_client.is_playing():
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
        ctx.guild.voice_client.pause()
        await ctx.respond(embed=discord.Embed(title="Pause", description="Song paused.", color=0x00ff00))

    @commands.slash_command(name="resume", description="Resumes the current song")
    async def resume(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not ctx.guild.voice_client.is_paused():
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="The song is not paused.", color=0xff0000))
        ctx.guild.voice_client.resume()
        await ctx.respond(embed=discord.Embed(title="Resume", description="Song resumed.", color=0x00ff00))

    @commands.slash_command(name="stop", description="Stops the current song")
    async def stop(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if not ctx.guild.voice_client.is_playing():
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="There is no song playing.", color=0xff0000))
        queue = await get_config(ctx.guild.id, False)
        await queue.set_position(0)
        await queue.edit_queue([])
        await queue.close()
        ctx.guild.voice_client.stop()
        await ctx.respond(embed=discord.Embed(title="Stop", description="Song stopped.", color=0x00ff00))


    @commands.slash_command(name="volume", description="Gets or sets the volume of the bot")
    async def volume(self, ctx: discord.ApplicationContext, volume: discord.Option(int, "The volume to set (from 0 to 100)", required=False)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if volume is not None:
            if volume > 100:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="Volume is too high.", color=0xff0000))
            if volume < 0:
                return await ctx.respond(
                    embed=discord.Embed(title="Error", description="Volume is too low.", color=0xff0000))
            ctx.guild.voice_client.source.volume = volume / 100
            queue = await get_config(ctx.guild.id, False)
            await queue.set_volume(ctx.guild.voice_client.source.volume)
            await queue.close()
            return await ctx.respond(embed=discord.Embed(title="Volume", description=f"Volume set to {volume}%",
                                                  color=0x00ff00))
            
        try:
            await ctx.respond(embed=discord.Embed(title="Volume",
                                                  description=f"Volume is {ctx.guild.voice_client.source.volume * 100}%",
                                                  color=0x00ff00))
        except:
            await ctx.respond(
                embed=discord.Embed(title="Error", description="Error while getting volume.", color=0xff0000))

    @commands.slash_command(name="record",
                            description="Enregistre nos chers gogols en train de chanter (c'est Rignchen qui m'as dit de laisser ça)")
    async def record(self, ctx: discord.ApplicationContext,
                     time: discord.Option(int, "Le temps d'enregistrement en secondes (de 1s à 260s)", required=True),
                     format: discord.Option(Sinks, "Le format d'enregistrement", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if time > 260:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Time is too long.", color=0xff0000))
        if time < 1:
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Time is too short.", color=0xff0000))
        vc = ctx.guild.voice_client
        if ctx.guild.id in connections.keys():
            return await ctx.respond(
                embed=discord.Embed(title="Error", description="Already recording", color=0xff0000))

        def finished_record():
            async def stop():
                vc.stop_recording()

            asyncio.run(stop())
            connections.pop(ctx.guild.id)

        if vc.channel.voice_states[vc.client.user.id].self_deaf:
            return await ctx.respond(embed=discord.Embed(title="Error", description="Bot is deafened.", color=0xff0000))
        timer = threading.Timer(time, finished_record)
        vc.start_recording(
            format.value,
            finished_record_callback,
            ctx.channel,
            sync_start=True
        )
        connections[ctx.guild.id] = vc
        users = []
        for user in vc.channel.members:
            if not user.bot:
                users.append(user.mention)
        if not users:
            users = ["No one will be recorded"]
        await ctx.respond(
            f"⚠ {', '.join(users)}, {ctx.author.mention} is recording you for {time} seconds",
            embed=discord.Embed(title="Record",
                                description=f"Recording for {time} seconds. The record will stop at <t:{int(time + datetime.now().timestamp())}:R>.",
                                color=0x00ff00))
        timer.start()

    @commands.slash_command(name="stop_record", description="Arrête l'enregistrement")
    async def stop_record(self, ctx: discord.ApplicationContext):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        try:
            ctx.guild.voice_client.stop_recording()
            connections.pop(ctx.guild.id).cancel()
            await ctx.respond(embed=discord.Embed(title="Stop record", description="Stopped recording.",
                                                  color=0x00ff00))
        except Exception as e:
            await ctx.respond(embed=discord.Embed(title="Error", description=f"Error while stopping recording: {e}",
                                                  color=0xff0000))


def setup(bot):
    bot.add_cog(State(bot))
