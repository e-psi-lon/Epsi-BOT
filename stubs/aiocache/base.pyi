from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from _typeshed import Incomplete
from aiocache import serializers as serializers
from aiocache.serializers import BaseSerializer

logger: Incomplete
SENTINEL: Incomplete

class API:
	CMDS: set[Callable[..., object]]
	@classmethod
	def register(cls, func): ...
	@classmethod
	def unregister(cls, func) -> None: ...
	@classmethod
	def timeout(cls, func): ...
	@classmethod
	def aiocache_enabled(cls, fake_return=None): ...
	@classmethod
	def plugins(cls, func): ...

class BaseCache:
	NAME: str
	timeout: float
	namespace: str | None
	ttl: int | None
	build_key: Incomplete
	def __init__(
		self,
		serializer: BaseSerializer | None = None,
		plugins: list[Any] | None = None,
		namespace: str | None = None,
		key_builder: Callable[[str, str | None], str] | None = None,
		timeout: float = 5,
		ttl: int | None = None,
	) -> None: ...
	@property
	def serializer(self) -> BaseSerializer: ...
	@serializer.setter
	def serializer(self, value: BaseSerializer) -> None: ...
	@property
	def plugins(self) -> list[Any]: ...
	@plugins.setter
	def plugins(self, value: list[Any]) -> None: ...
	async def add(
		self, key, value, ttl=..., dumps_fn=None, namespace=None, _conn=None
	): ...
	async def get(
		self,
		key: str,
		default: Any = None,
		loads_fn: Callable[[Any], Any] | None = None,
		namespace: str | None = None,
		_conn: Any = None,
	) -> Any: ...
	async def multi_get(
		self,
		keys: list[str],
		loads_fn: Callable[[Any], Any] | None = None,
		namespace: str | None = None,
		_conn: Any = None,
	): ...
	async def set(
		self,
		key: str,
		value: Any,
		ttl: int | None = ...,
		dumps_fn: Callable[[Any], Any] | None = None,
		namespace: str | None = None,
		_cas_token: Any = None,
		_conn: Any = None,
	) -> bool: ...
	async def multi_set(
		self, pairs, ttl=..., dumps_fn=None, namespace=None, _conn=None
	): ...
	async def delete(
		self, key: str, namespace: str | None = None, _conn: Any = None
	) -> int: ...
	async def exists(
		self, key: str, namespace: str | None = None, _conn: Any = None
	) -> bool: ...
	async def increment(self, key, delta: int = 1, namespace=None, _conn=None): ...
	async def expire(
		self, key: str, ttl: int, namespace: str | None = None, _conn: Any = None
	): ...
	async def clear(self, namespace: str | None = None, _conn: Any = None): ...
	async def raw(self, command, *args, _conn=None, **kwargs): ...
	async def close(self, *args: Any, _conn: Any = None, **kwargs: Any) -> None: ...
	def get_connection(self): ...
	async def acquire_conn(self): ...
	async def release_conn(self, conn) -> None: ...
	async def __aenter__(self) -> Self: ...
	async def __aexit__(
		self,
		exc_type: type[BaseException] | None,
		exc: BaseException | None,
		tb: TracebackType | None,
	) -> None: ...

class _Conn:
	def __init__(self, cache) -> None: ...
	async def __aenter__(self): ...
	async def __aexit__(self, exc_type, exc_value, traceback) -> None: ...
	def __getattr__(self, name): ...
