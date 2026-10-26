from typing import Any

from _typeshed import Incomplete

logger: Incomplete

class BaseSerializer:
	DEFAULT_ENCODING: str | None
	encoding: str | None
	def __init__(
		self, *args: Any, encoding: str | None = ..., **kwargs: Any
	) -> None: ...
	def dumps(self, value: Any) -> Any: ...
	def loads(self, value: Any) -> Any: ...

class JsonSerializer(BaseSerializer):
	def dumps(self, value: Any) -> str: ...
	def loads(self, value: str | None) -> Any: ...
