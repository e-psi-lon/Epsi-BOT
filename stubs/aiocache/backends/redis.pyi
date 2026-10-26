from typing import Any, ClassVar, Self

from aiocache.base import BaseCache as BaseCache
from aiocache.serializers import BaseSerializer, JsonSerializer as JsonSerializer
from redis.asyncio import Redis

class RedisBackend(BaseCache):
	RELEASE_SCRIPT: ClassVar[str]
	CAS_SCRIPT: ClassVar[str]
	endpoint: str
	port: int
	db: int
	password: str | None
	pool_max_size: int | None
	create_connection_timeout: float | None
	client: Redis
	def __init__(
		self,
		endpoint: str = "127.0.0.1",
		port: int = 6379,
		db: int = 0,
		password=None,
		pool_min_size=...,
		pool_max_size=None,
		create_connection_timeout=None,
		ssl: bool = False,
		connection_pool_class=None,
		connection_pool_kwargs=None,
		**kwargs,
	) -> None: ...

class RedisCache(RedisBackend):
	NAME: str
	def __init__(
		self,
		serializer: BaseSerializer | None = None,
		**kwargs: Any,
	) -> None: ...
	@classmethod
	def parse_uri_path(cls, path: str) -> dict[str, str]: ...
	async def __aenter__(self) -> Self: ...
