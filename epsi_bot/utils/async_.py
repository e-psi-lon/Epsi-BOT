import asyncio
import concurrent.futures
from multiprocessing import Event as _Event
from typing import Literal, Optional, Union, Callable, Coroutine, Any

import aiohttp

from .loggers import get_logger

__all__ = ["run_sync", "run_async", "AsyncRequests", "Event", "set_callback"]


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

class AsyncRequests:
	"""
	Class to make asynchronous requests

	Methods
	-------
	get
		Make a GET request
	post
		Make a POST request
	"""

	@staticmethod
	async def get(url: str, params: Optional[dict] = None, data: Any = None, headers: Optional[dict] = None,
				  cookies: Optional[dict] = None, auth: Optional[aiohttp.BasicAuth] = None,
				  allow_redirects: bool = True, timeout: aiohttp.ClientTimeout | aiohttp.helpers._SENTINEL | None = None, json: Any = None,
				  return_type: Literal["json", "text", "content"] = "json") -> Union[dict, str, bytes]:
		"""
		Make a GET request
		
		Parameters
		----------
		url : str
			The URL to make the request to.
		params : Optional[dict]
			The parameters for the request. Default is None.
		data : Any
			The data for the request. Default is None.
		headers : Optional[dict]
			The headers for the request. Default is None.
		cookies : Optional[dict]
			The cookies for the request. Default is None.
		auth : Optional[aiohttp.BasicAuth]
			The authentication data for the request. Default is None.
		allow_redirects : bool
			Whether to allow redirects or not. Default is True.
		timeout : Optional[float]
			The timeout for the request. Default is None.
		json : Any
			The json data for the request. Default is None.
		return_type : Literal["json", "text", "content"]
			The type of the return value. Default is "json".
		
		Returns
		-------
		Union[dict, str, bytes]
			The response of the request
		"""
		async with aiohttp.ClientSession() as session:
			async with session.get(url, params=params, data=data, headers=headers, cookies=cookies, auth=auth,
								   allow_redirects=allow_redirects, timeout=timeout, json=json) as response:
				response.raise_for_status()
				match return_type:
					case "json":
						return await response.json()
					case "content":
						return await response.content.read()
					case _:
						return await response.text()

	@staticmethod
	async def post(url: str, data: Any = None, json: Any = None, params: Optional[dict] = None,
				   headers: Optional[dict] = None, cookies: Optional[dict] = None,
				   auth: Optional[aiohttp.BasicAuth] = None, allow_redirects: bool = True,
				   timeout: aiohttp.ClientTimeout | aiohttp.helpers._SENTINEL | None = None, return_type: Literal["json", "text", "content"] = "json") \
			-> Union[dict, str, bytes]:
		"""
		Make a POST request
		
		Parameters
		----------
		url : str
			The URL to make the request to.
		data : Any
			The data for the request. Default is None.
		json : Any
			The json data for the request. Default is None.
		params : Optional[dict]
			The parameters for the request. Default is None.
		headers : Optional[dict]
			The headers for the request. Default is None.
		cookies : Optional[dict]
			The cookies for the request. Default is None.
		auth : Optional[aiohttp.BasicAuth]
			The authentication data for the request. Default is None.
		allow_redirects : bool
			Whether to allow redirects or not. Default is True.
		timeout : Optional[float]
			The timeout for the request. Default is None.
		return_type : Literal["json", "text", "content"]
			The type of the return value. Default is "json".
		"""
		async with aiohttp.ClientSession() as session:
			async with session.post(url, data=data, json=json, params=params, headers=headers, cookies=cookies,
									auth=auth, allow_redirects=allow_redirects, timeout=timeout) as response:
				response.raise_for_status()
				match return_type:
					case "json":
						return await response.json()
					case "content":
						return await response.content.read()
					case _:
						return await response.text()

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
	

async def set_callback(event: Event, callback: Callable[[], Coroutine[Any, Any, None]], event_loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
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