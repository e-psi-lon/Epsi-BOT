from typing import Optional, cast, Any
import aiomcache
from aiocache import MemcachedCache  # type: ignore[import-untyped]
from aiocache.serializers import PickleSerializer  # type: ignore[import-untyped]

from epsi_bot.panel.PanelProtocol import PanelProtocol


async def get_cache_stats() -> Optional[dict[bytes, bytes]]:
	"""Get memcached statistics."""
	mc = aiomcache.Client("127.0.0.1", 11211)
	try:
		stats = await mc.stats()
		return {key: value for key, value in stats.items() if value is not None}
	finally:
		await mc.close()

async def get_from_bot_cached(channel: str, **payload: dict[str, Any] | Any | None) -> Any:
	"""Get data from bot with caching."""
	async with MemcachedCache(serializer=PickleSerializer(), namespace="ipc_cache") as cache:
		cache_key = f"{channel}_{payload}"
		if await cache.exists(cache_key):
			return await cache.get(cache_key)
		else:
			from quart import current_app
			panel_app = cast(PanelProtocol, current_app)
			response = await panel_app.bot_ipc.request(channel, timeout=5.,  **payload)
			await cache.set(cache_key, response, ttl=60)
			return response