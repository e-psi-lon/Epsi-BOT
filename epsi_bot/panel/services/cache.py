from typing import Optional
import aiomcache
from aiocache import MemcachedCache
from aiocache.serializers import PickleSerializer

async def get_cache_stats() -> Optional[dict[bytes, bytes]]:
	"""Get memcached statistics."""
	mc = aiomcache.Client("127.0.0.1", 11211)
	try:
		stats = await mc.stats()
		return stats
	finally:
		await mc.close()

async def get_from_bot_cached(channel: str, **payload):
	"""Get data from bot with caching."""
	async with MemcachedCache(serializer=PickleSerializer(), namespace="ipc_cache") as cache:
		cache_key = f"{channel}_{payload}"
		if await cache.exists(cache_key):
			return await cache.get(cache_key)
		else:
			from quart import current_app
			response = await current_app.bot_ipc.request(channel, **payload)
			await cache.set(cache_key, response, ttl=60)
			return response