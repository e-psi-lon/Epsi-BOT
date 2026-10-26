from collections.abc import Callable
from enum import Enum
from typing import Any, cast

import discord
from discord import commands as base_commands, interactions
from discord.ext import commands

__all__ = ["FfmpegFormats", "GuildMessageable", "Sinks", "get_channel", "get_guild"]

GuildMessageable = discord.TextChannel | discord.VoiceChannel | discord.StageChannel


class Sinks(Enum):
	"""Enum for the different types of audio sinks"""

	_value_: type[discord.sinks.Sink]
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


def option[F: Callable[..., Any]](
	name: str,
	input_type: base_commands.options.InputType | None = None,
	**kwargs: Any,
) -> Callable[[F], F]:
	return cast(Callable[[F], F], discord.option(name, input_type, **kwargs))


def get_channel(ctx: discord.ApplicationContext) -> interactions.InteractionChannel:
	"""Get the channel from the context"""
	if (channel := ctx.channel) is None:
		raise commands.ChannelNotFound("Couldn't find the channel.")
	return channel


def get_guild(ctx: discord.ApplicationContext) -> discord.Guild:
	"""Get the guild from the context"""
	if (guild := ctx.guild) is None:
		raise commands.NoPrivateMessage("This command cannot be used in DMs.")
	return guild
