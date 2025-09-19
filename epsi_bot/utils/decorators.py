from functools import wraps
from typing import Any, TypeVar, Callable, Awaitable

from quart import session, redirect, url_for, request, websocket


__all__ = ["login_required", "admin_required"]

T = TypeVar("T")


def login_required(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
	"""Decorator to require user authentication."""

	@wraps(f)
	async def decorated_function(*args: Any, **kwargs: Any) -> Any:
		if "token" not in session:
			return redirect(url_for("auth.login"))
		return await f(*args, **kwargs)

	return decorated_function


def admin_required(f: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
	"""Decorator to require admin access (local network only)."""

	@wraps(f)
	async def decorated_function(*args: Any, **kwargs: Any) -> Any:
		# For regular routes
		remote_addr: str
		if hasattr(request, "remote_addr") and request.remote_addr is not None:
			remote_addr = request.remote_addr
		# For websockets
		elif hasattr(websocket, "remote_addr") and websocket.remote_addr is not None:
			remote_addr = websocket.remote_addr
		else:
			return 403

		if not remote_addr.startswith("192.168.83.") and remote_addr != "127.0.0.1":
			return 403
		return await f(*args, **kwargs)

	return decorated_function
