import asyncio
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Any, Callable, Coroutine, Optional
from multiprocessing import Queue, Event as Event
from multiprocessing.synchronize import Event as EventClass
import uuid

from .loggers import get_logger


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
		threading.Thread(target=self._sync_reader, name=f"IPCManager-{self._side}", args=(asyncio.get_event_loop(),)).start()

	def _sync_reader(self, loop):
		while self._running:
			msg = self._in_queue.get()
			loop.call_soon_threadsafe(self._async_in_queue.put_nowait, msg)


	async def _process_queue(self):
		while self._running:
			msg = await self._async_in_queue.get()
			self._logger.info(f"Received message: {msg}")
			if msg.type == MessageType.RESPONSE:
				async with self._pending_lock:
					self._logger.info(f"Received response for {msg.id}")
					self._logger.info(f"Pending requests: {self._pending_requests}")
					pending_requests = self._pending_requests
					if msg.id in pending_requests:
						self._logger.info(f"Resolving future for {msg.id}")
						future = pending_requests.pop(msg.id)
						future.set_result(msg.payload)
			elif msg.channel in self._handlers:
				self._logger.info(f"Handling message for {msg.channel}")
				if isinstance(msg.payload, dict):
					await self._handlers[msg.channel](msg.id, **msg.payload)
				elif msg.payload is None:
					await self._handlers[msg.channel](msg.id)
				else:
					await self._handlers[msg.channel](msg.id, msg.payload)



	async def send(self, channel: str, payload: Any = None):
		msg = IPCMessage(MessageType.EVENT, channel, payload)
		self._logger.info(f"Sending event: {msg}")
		self._out_queue.put(msg)
		self._event.set()
	
	async def request(self, channel: str, payload: Optional[Any] = None, timeout: float = 5.0) -> Any:
		"""Make a request on a channel and wait for response
		
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
			If no response received within timeout period
		"""
		msg = IPCMessage(MessageType.REQUEST, channel, payload)
		request_id = msg.id
		future = asyncio.Future()
		async with self._pending_lock:
			self._pending_requests[request_id] = future
		self._logger.info(f"Sending request with id {request_id}")
		self._logger.info(f"Pending requests: {self._pending_requests}")
		self._out_queue.put(msg)
		self._event.set()
		try:
			return await asyncio.wait_for(future, timeout)
		except asyncio.TimeoutError:
			self._logger.warning(f"Request {request_id} timed out after {timeout}s")
			async with self._pending_lock:
				self._pending_requests.pop(request_id, None)
			raise
		except Exception as e:
			self._logger.error(f"Error for {request_id}: {e}")
			async with self._pending_lock:
				self._pending_requests.pop(request_id, None)
			raise


	async def respond(self, id: str, payload: Any):
		self._logger.info(f"Sending response for {id}")
		msg = IPCMessage(MessageType.RESPONSE, "", payload, id)
		self._out_queue.put(msg)
		self._event.set()

	def handle(self, channel: str):
		"""Register a handler for a specific channel.
		The handler function have to be a coroutine that takes two 
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
		self._logger.info(f"Registering handler for channel {channel}")
		
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