from enum import Enum

import discord

__all__ = ["FfmpegFormats", "Sinks"]


class Sinks(Enum):
	"""Enum for the different types of audio sinks"""

	mp3 = discord.sinks.MP3Sink()
	wav = discord.sinks.WaveSink()
	ogg = discord.sinks.OGGSink()
	mp4 = discord.sinks.MP4Sink()


class FfmpegFormats(Enum):
	MP3 = ("-codec:a", "libmp3lame")
	FLAC = ("-codec:a", "flac", "-sample_fmt", "s16")
	OGG = ("-codec:a", "libvorbis")
	OPUS = ("-codec:a", "libopus")
	M4A = ("-codec:a", "aac")
	WAV = ("-codec:a", "pcm_s16le")
