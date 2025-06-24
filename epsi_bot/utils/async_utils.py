import asyncio
import concurrent.futures
from multiprocessing import Event as _Event
from typing import Literal, Optional, Union, Callable, Coroutine, Any

import aiohttp

from epsi_bot.utils.loggers import get_logger

__all__ = ["run_sync", "run_async", "Event", "set_callback"]


def run_sync(coro: Coroutine) -> Any:
	"""
	Run a coroutine synchronously
	
	Parameters
	----------
	coro : Coroutine
		The coroutine to run
		
	Returns
	-------
	Any
		The result of the coroutine
	"""
	with concurrent.futures.ThreadPoolExecutor() as pool:
		future = pool.submit(asyncio.run, coro)
		concurrent.futures.wait([future])
		return future.result()


async def run_async(func: Callable) -> Any:
	"""
	Run a synchronous function asynchronously
	
	Parameters
	----------
	func : Callable
		The function to run
	
	Returns
	-------
	Any
		The result of the function
	"""
	return await asyncio.get_event_loop().run_in_executor(None, func)


class Event:
	def __init__(self) -> None:
		self._event = _Event()
		self.is_response: Optional[bool] = None

	async def wait(self, timeout: Optional[float] = None) -> None:
		if timeout is None:
			await asyncio.get_event_loop().run_in_executor(None, self._event.wait)
		else:
			await asyncio.get_event_loop().run_in_executor(None, self._event.wait, timeout)

	def __await__(self) -> Any:
		return self.wait().__await__()

	async def set(self, is_response: bool = False) -> None:
		self._event.set()
		self.is_response = is_response

	async def clear(self) -> None:
		self._event.clear()
		self.is_response = None

	def is_set(self) -> bool:
		return self._event.is_set()

	def __repr__(self) -> str:
		return f"<Event {'set' if self.is_set() else 'clear'} is_response={self.is_response}>"


async def set_callback(event: Event, callback: Callable[..., Coroutine[Any, Any, None]],
                       event_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
	"""
	Set a callback to be called when the event is set.

	Parameters
	----------
	event : Event
		The event to wait for.
	callback : Callable[[], Coroutine[Any, Any, None]]
		The callback to call when the event is set.
	event_loop : Optional[asyncio.AbstractEventLoop]
		The event loop to run the callback in. Default is None.

	Returns
	-------
	None
	"""

	async def _callback() -> None:
		while True:
			await event.wait()
			if not event.is_response:
				await callback()
				get_logger("Callback").debug(f"The callback for {event} is being called")
				await event.clear()

	asyncio.run_coroutine_threadsafe(_callback(), event_loop or asyncio.get_event_loop())
