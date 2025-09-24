import asyncio
import io
import logging
from math import log
from typing import Any, Coroutine, Optional, cast

import binascii
import aiomcache
import pytubefix  # type: ignore[import-untyped]
import zlib
from aiocache import MemcachedCache  # type: ignore[import-untyped]
from aiocache.serializers import JsonSerializer, PickleSerializer  # type: ignore[import-untyped]

from epsi_bot.utils.protocols import CacheProtocol, PanelProtocol
import epsi_bot.utils.requests as requests
from epsi_bot.utils.constants import YOUTUBE_REGEX, YOUTUBE_CLIENT
from epsi_bot.utils.loggers import get_logger

__all__ = ["AudioCache", "download", "download_bulk", "get_cache_stats", "get_from_bot_cached"]


class AudioCache(MemcachedCache, CacheProtocol):
	"""Class to manage the audio cache"""

	def __init__(self, scale_factor: int = 5):
		if scale_factor < 1:
			scale_factor = 1
		super().__init__(
			serializer=Base64Serializer(),
			namespace="audio",
			endpoint="127.0.0.1",
			port=11211,
			pool_size=max(1, min(int(scale_factor ** 0.5), 10)),
			timeout=15,
		)
		self.logger = get_logger("Memcached Audio Cache")

	async def get_audio(self, key: str, **_: Any) -> io.BytesIO | None:
		"""Get a value from the cache"""
		return (await super().get(key)) or None

	async def set_audio(
		self, key: str, value: io.BytesIO, ttl: int = 3600, **_: Any
	) -> None:
		"""Set a value in the cache"""
		await super().set(key, value, ttl=ttl)
		self.logger.debug(f"Set {key} in cache")

	async def exists(
		self, key: str, namespace: Any | None = None, _conn: Any | None = None
	) -> Any:
		"""Check if a key exists in the cache"""
		return await super().exists(key, namespace=namespace, _conn=_conn)

	async def update_ttl(self, key: str, new_ttl: int) -> None:
		"""Update the ttl of a key in the cache"""
		key = self.build_key(key, namespace=self.namespace)
		await self.client.touch(key.encode(), new_ttl)

	async def clear(
		self, namespace: Any | None = None, _conn: Any | None = None
	) -> None:
		"""Clear the cache"""
		await super().clear(namespace=namespace, _conn=_conn)

	def __aenter__(self) -> Coroutine[Any, Any, "AudioCache"]:
		return super().__aenter__()

	def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
		return super().__aexit__(exc_type, exc_val, exc_tb)


async def get_or_download_audio(url: str, cache: AudioCache) -> io.BytesIO:
	data = await cache.get_audio(url)
	if data is not None:
		return data
	buffer = io.BytesIO()
	buffer.seek(0)
	if not YOUTUBE_REGEX.match(url):
		result = await requests.get(url, return_type="content")
		if not isinstance(result, bytes):
			raise TypeError(f"Expected bytes, got {type(result)} for url {url}")
		buffer.write(result)
	else:
		try:
			yt_video = pytubefix.YouTube(url, client=YOUTUBE_CLIENT)
			stream = await asyncio.to_thread(yt_video.streams.get_audio_only)
			await asyncio.to_thread(stream.stream_to_buffer, buffer)
		except Exception as e:
			buffer.close()
			raise e
	buffer.seek(0)
	await cache.set_audio(url, buffer, ttl=3600)
	return buffer


class Base64Serializer(JsonSerializer):
	def dumps(self, value: Any) -> str:
		if isinstance(value, io.BytesIO):
			logger = get_logger("Memcached")
			logger.debug(f"Audio size: {len(value.getvalue())} bytes")
			compressed = zlib.compress(value.getvalue())
			logger.debug(f"Compressed audio size: {len(compressed)} bytes")
			return binascii.hexlify(compressed).decode()
		return super().dumps(value)

	def loads(self, value: str) -> io.BytesIO | Any:
		try:
			val = io.BytesIO(zlib.decompress(binascii.unhexlify(value.encode())))
			val.seek(0)
			return val
		except (TypeError, binascii.Error, zlib.error, AttributeError):
			return super().loads(value)


async def download(
	url: str, download_logger: logging.Logger = get_logger("Audio-Downloader")
) -> io.BytesIO:
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
		value = await get_or_download_audio(url, cache)
	download_logger.info(f"Successfully downloaded {url}")
	return value


async def download_bulk(
	urls: list[str], download_logger: logging.Logger = get_logger("Audio-Downloader")
) -> list[io.BytesIO]:
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
	semaphore_size = max(2, min(int(2 * log(len(urls) + 1, 2)), 8))
	semaphore = asyncio.Semaphore(semaphore_size)


	async def download_worker(url: str, cache_: AudioCache) -> io.BytesIO:
		async with semaphore:
			result = await get_or_download_audio(url, cache_)
			download_logger.info(f"Downloaded {url}")
			return result

	async with AudioCache(len(urls)) as cache:
		tasks = [download_worker(url, cache) for url in urls]
		results = await asyncio.gather(*tasks)
		return results


async def get_cache_stats() -> Optional[dict[bytes, bytes]]:
	"""Get memcached statistics."""
	mc = aiomcache.Client("127.0.0.1", 11211)
	try:
		stats = await mc.stats()
		return {key: value for key, value in stats.items() if value is not None}
	finally:
		await mc.close()


async def get_from_bot_cached(
	channel: str, **payload: dict[str, Any] | Any | None
) -> Any:
	"""Get data from bot with caching."""
	async with MemcachedCache(
		serializer=PickleSerializer(), namespace="ipc_cache"
	) as cache:
		cache_key = f"{channel}_{payload}"
		if await cache.exists(cache_key):
			return await cache.get(cache_key)
		else:
			from quart import current_app

			panel_app = cast(PanelProtocol, current_app)
			response = await panel_app.bot_ipc.request(channel, timeout=5.0, **payload)
			await cache.set(cache_key, response, ttl=60)
			return response