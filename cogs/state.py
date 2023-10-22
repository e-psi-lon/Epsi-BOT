import threading

import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
from utils import *
import pytube
import asyncio

connections = {}


class State(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="play", description="Plays the audio of a YouTube video")
    async def play(self, ctx: discord.ApplicationContext,
                   query: discord.Option(str, "The YouTube audio to play", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        try:
            url = pytube.YouTube(query).watch_url
            try:
                queue = get_queue(ctx.guild.id)
                if not queue['queue']:
                    queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                    update_queue(ctx.guild.id, queue)
                    await ctx.respond(embed=discord.Embed(title="Play",
                                                          description=f"Playing song [{pytube.YouTube(url).title}]({url})",
                                                          color=0x00ff00))
                    await play_song(ctx, url)
                    return await asyncio.sleep(1)
                queue['queue'].append({'title': pytube.YouTube(query).title, 'url': url})
                update_queue(ctx.guild.id, queue)
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
                embed=discord.Embed(title="Select audio", description="Select an audio to play", color=0x00ff00),
                view=view)

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
            await ctx.respond(embed=discord.Embed(title="Volume",
                                                  description=f"Volume is {ctx.guild.voice_client.source.volume * 100}%",
                                                  color=0x00ff00))
        except:
            await ctx.respond(
                embed=discord.Embed(title="Error", description="Error while getting volume.", color=0xff0000))

    @commands.slash_command(name="record", description="Enregistre nos chers gogols en train de chanter (c'est Rignchen qui m'as dit de laisser ça)")
    async def record(self, ctx: discord.ApplicationContext,
                     time: discord.Option(int, "Le temps d'enregistrement en secondes (de 1s à 260s)", required=True),
                     format: discord.Option(Sinks, "Le format d'enregistrement", required=True)):
        if ctx.guild.voice_client is None:
            return await ctx.respond(embed=EMBED_ERROR_BOT_NOT_CONNECTED)
        if time > 260:
            return await ctx.respond(embed=discord.Embed(title="Error", description="Time is too long.", color=0xff0000))
        if time < 1:
            return await ctx.respond(embed=discord.Embed(title="Error", description="Time is too short.", color=0xff0000))
        vc = ctx.guild.voice_client
        if ctx.guild.id in connections.keys():
            return await ctx.respond(embed=discord.Embed(title="Error", description="Already recording", color=0xff0000))
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
            ctx.channel
        )
        connections[ctx.guild.id] = vc
        await ctx.respond(
            embed=discord.Embed(title="Record", description=f"Recording for {time} seconds. The record will stop at <t:{int(time + timer.interval)}>.", color=0x00ff00))
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
