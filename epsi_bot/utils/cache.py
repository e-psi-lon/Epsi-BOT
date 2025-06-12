import asyncio
import base64
import io
import logging
from typing import Any, Coroutine

import binascii
import pytubefix  # type: ignore[import-untyped]
import zlib
from aiocache import MemcachedCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer

from epsi_bot.utils.async_utils import AsyncRequests
from epsi_bot.utils.constants import YOUTUBE_REGEX, YOUTUBE_CLIENT
from epsi_bot.utils.loggers import get_logger

__all__ = ["AudioCache", "download", "download_bulk"]


class AudioCache(MemcachedCache):
	"""Class to manage the audio cache"""

	def __init__(self, pool_size: int = 5):
		super().__init__(
			serializer=AudioCache.Base64Serializer(),
			namespace="audio",
			endpoint="127.0.0.1",
			port=11211,
			pool_size=pool_size,
			timeout=15
		)
		self.logger = get_logger("Memcached Audio Cache")

	async def get(self, key: str, **_: Any) -> io.BytesIO | None:
		"""Get a value from the cache"""
		return (await super().get(key)) or None

	async def set(self, key: str, value: io.BytesIO, ttl: int = 3600, **_: Any) -> None:
		"""Set a value in the cache"""
		await super().set(key, value, ttl=ttl)
		self.logger.debug(f"Set {key} in cache")

	async def exists(self, key: str, **_: Any) -> bool:
		"""Check if a key exists in the cache"""
		return await super().exists(key)

	def update_ttl(self, key: str, new_ttl: int) -> None:
		"""Update the ttl of a key in the cache"""
		key = self.build_key(key, namespace=self.namespace)
		self.client.touch(key.encode(), new_ttl)

	async def clear(self, **_: Any) -> None:
		"""Clear the cache"""
		await super().clear()

	def __aenter__(self) -> Coroutine[Any, Any, "AudioCache"]:
		return super().__aenter__()

	def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
		return super().__aexit__(exc_type, exc_val, exc_tb)

	class Base64Serializer(JsonSerializer):
		def dumps(self, value):
			if isinstance(value, io.BytesIO):
				logger = get_logger("Memcached")
				logger.debug(f"Audio size: {len(value.getvalue())} bytes")
				compressed = zlib.compress(base64.b64encode(value.getvalue()))
				logger.debug(f"Compressed audio size: {len(compressed)} bytes")
				return binascii.hexlify(compressed).decode()
			return super().dumps(value)

		def loads(self, value: str):
			try:
				val = io.BytesIO(base64.b64decode(zlib.decompress(binascii.unhexlify(value.encode()))))
				val.seek(0)
				return val
			except (TypeError, binascii.Error, zlib.error, AttributeError):
				return super().loads(value)


async def to_cache(url: str, cache: AudioCache) -> io.BytesIO:
	data = await cache.get(url)
	if data is not None:
		return data
	buffer = io.BytesIO()
	buffer.seek(0)
	if not YOUTUBE_REGEX.match(url):
		r: bytes = await AsyncRequests.get(url, return_type="content")
		buffer.write(r)
	else:
		yt_video = pytubefix.YouTube(url, client=YOUTUBE_CLIENT)
		stream = await asyncio.to_thread(yt_video.streams.get_audio_only)
		await asyncio.to_thread(stream.stream_to_buffer, buffer)
	buffer.seek(0)
	await cache.set(url, buffer, ttl=3600)
	return buffer


async def download(url: str, download_logger: logging.Logger = get_logger("Audio-Downloader")) -> io.BytesIO:
	"""
	Download a video from a YouTube (or other) URL.
	
	Parameters
	----------
	url : str
		The URL of the video to download
	download_logger : logging.Logger
		The logger to log the download
	
	Returns
	-------
	Optional[io.BytesIO]
		The downloaded video
	"""
	async with AudioCache() as cache:
		value = await to_cache(url, cache)
	download_logger.info(f"Successfully downloaded {url}")
	return value


async def download_bulk(urls: list[str], download_logger: logging.Logger = get_logger("Audio-Downloader")) -> list[
	io.BytesIO]:
	"""
	Download a list of videos from YouTube (or other) URLs in bulk.
	
	Parameters
	----------
	urls : list[str]
		The URLs of the videos to download
	download_logger : logging.Logger
		The logger to log the download
	
	Returns
	-------
	list[io.BytesIO]
		The downloaded videos
	"""

	async def download_worker(url: str, cache_) -> io.BytesIO:
		result = await to_cache(url, cache_)
		download_logger.info(f"Downloaded {url}")
		return result

	async with AudioCache(len(urls)) as cache:
		tasks = [download_worker(url, cache) for url in urls]
		results = await asyncio.gather(*tasks)
		return results
