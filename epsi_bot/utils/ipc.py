import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import Queue, Event as Event
from multiprocessing.synchronize import Event as EventClass
from typing import Any, Callable, Coroutine, Optional

from epsi_bot.utils.loggers import get_logger

__all__ = ["IPCMessage", "IPCManager", "MessageType"]


class MessageType(Enum):
	EVENT = "event"
	DATA = "data"
	REQUEST = "request"
	RESPONSE = "response"


@dataclass
class IPCMessage:
	type: MessageType
	channel: str
	payload: Any
	id: str = field(default_factory=lambda: str(uuid.uuid4()))


class IPCManager:
	def __init__(self, side: str, in_queue: Queue, out_queue: Queue, event: Optional[EventClass] = None):
		self._in_queue: Queue[IPCMessage] = in_queue
		self._async_in_queue: asyncio.Queue[IPCMessage] = asyncio.Queue()
		self._out_queue: Queue[IPCMessage] = out_queue
		self._handlers: dict[str, Callable[[str, Any], Coroutine]] = {}
		self._running = True
		self._event: EventClass = event or Event()
		self._logger = get_logger(f"IPC [{side}]")
		self._pending_requests: dict[str, asyncio.Future] = {}
		self._side = side
		self._thread = None
		self._pending_lock = asyncio.Lock()

	async def start(self):
		self._logger.info(f"Starting IPCManager for {self._side}")
		asyncio.create_task(self._process_queue())
		threading.Thread(target=self._sync_reader, name=f"IPCManager-{self._side}",
		                 args=(asyncio.get_event_loop(),)).start()

	def _sync_reader(self, loop):
		while self._running:
			msg = self._in_queue.get()
			loop.call_soon_threadsafe(self._async_in_queue.put_nowait, msg)

	async def _process_queue(self):
		while self._running:
			msg = await self._async_in_queue.get()
			self._logger.debug(f"Received message: {msg}")
			if msg.type == MessageType.RESPONSE:
				async with self._pending_lock:
					self._logger.debug(f"Received response for {msg.id}")
					pending_requests = self._pending_requests
					if msg.id in pending_requests:
						self._logger.debug(f"Resolving future for {msg.id}")
						future = pending_requests.pop(msg.id)
						future.set_result(msg.payload)
			elif msg.channel in self._handlers:
				self._logger.debug(f"Handling message for {msg.channel}")
				if isinstance(msg.payload, dict):
					await self._handlers[msg.channel](msg.id, **msg.payload)
				elif msg.payload is None:
					await self._handlers[msg.channel](msg.id)
				else:
					await self._handlers[msg.channel](msg.id, msg.payload)

	async def send(self, channel: str, payload: Any = None):
		msg = IPCMessage(MessageType.EVENT, channel, payload)
		self._logger.debug(f"Sending event: {msg}")
		self._out_queue.put(msg)
		self._event.set()

	async def request(self, channel: str, timeout: float = 5.0, **payload: Optional[Any]) -> Any:
		"""Make a request on a channel and wait for the response

		Parameters
		----------
		channel : str
			The channel to send request to
		payload : Optional[Any]
			The payload to send
		timeout : float, default=5.0
			Maximum time to wait for response in seconds

		Returns
		-------
		Any
			The response payload

		Raises
		------
		asyncio.TimeoutError
			If no response is received within the timeout period
		"""
		if not payload:
			payload = None
		elif len(payload) == 1:
			payload = next(iter(payload.values()))
		msg = IPCMessage(MessageType.REQUEST, channel, payload)
		request_id = msg.id
		future = asyncio.Future()
		async with self._pending_lock:
			self._pending_requests[request_id] = future
		self._logger.debug(f"Sending request with id {request_id}")
		self._out_queue.put(msg)
		self._event.set()
		try:
			return await asyncio.wait_for(future, timeout)
		except asyncio.TimeoutError:
			self._logger.warning(f"Request {request_id} timed out after {timeout}s")
			async with self._pending_lock:
				await self._pending_requests.pop(request_id, None)
			raise
		except Exception as e:
			self._logger.error(f"Error for {request_id}: {e}")
			async with self._pending_lock:
				await self._pending_requests.pop(request_id, None)
			raise

	async def respond(self, request_id: str, payload: Any):
		self._logger.debug(f"Sending response for {request_id}")
		msg = IPCMessage(MessageType.RESPONSE, "", payload, request_id)
		self._out_queue.put(msg)
		self._event.set()

	def handle(self, channel: str):
		"""Register a handler for a specific channel.
		The handler function has to be a coroutine that takes two
		parameters: the id of the message and the payload.

		Parameters
		----------
		channel : str
			The channel to register the handler for

		Returns
		-------
		Callable
			The decorator function that will register the handler
		"""
		self._logger.debug(f"Registering handler for channel {channel}")

		def decorator(func: Callable[[str, Any], Coroutine]):
			if channel in self._handlers:
				self._logger.warning(f"Overwriting handler for channel {channel}")
			self._handlers[channel] = func
			return func

		return decorator

	def stop(self):
		self._logger.info("Stopping IPCManager")
		self._running = False
		self._event.set()

	@classmethod
	def create_pair(cls) -> tuple["IPCManager", "IPCManager"]:
		in_queue = Queue()
		out_queue = Queue()
		event = Event()
		return (
			cls("panel", in_queue, out_queue, event),
			cls("bot", out_queue, in_queue, event)
		)
