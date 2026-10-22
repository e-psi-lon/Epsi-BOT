from enum import Enum

import discord
from discord.ext import commands

__all__ = ["FfmpegFormats", "Sinks", "get_guild"]


class Sinks(Enum):
	"""Enum for the different types of audio sinks"""

	mp3 = discord.sinks.MP3Sink
	wav = discord.sinks.WaveSink
	ogg = discord.sinks.OGGSink
	mp4 = discord.sinks.MP4Sink

	def sink(self) -> discord.sinks.Sink:
		"""Get the sink class for the given sink type"""
		return self.value()


class FfmpegFormats(Enum):
	MP3 = ("-codec:a", "libmp3lame")
	FLAC = ("-codec:a", "flac", "-sample_fmt", "s16")
	OGG = ("-codec:a", "libvorbis")
	OPUS = ("-codec:a", "libopus")
	M4A = ("-codec:a", "aac")
	WAV = ("-codec:a", "pcm_s16le")


def get_guild(ctx: discord.ApplicationContext) -> discord.Guild:
	"""Get the guild from the context"""
	if ctx.guild is None:
		raise commands.NoPrivateMessage("This command cannot be used in DMs.")
	return ctx.guild