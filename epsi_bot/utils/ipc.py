import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from multiprocessing import Queue
import uuid

from .async_utils import Event
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
	def __init__(self, side: str, in_queue: Optional[Queue] = None, out_queue: Optional[Queue] = None, event: Optional[Event] = None):
		self._in_queue = in_queue or Queue()
		self._out_queue = out_queue or Queue()
		self._handlers: dict[str, Callable[[str, Any], Coroutine]] = {}
		self._running = True
		self._event: Event = event or Event()
		self._logger = get_logger(f"IPC ({side})")
		self._pending_requests: dict[str, asyncio.Future] = {}
		self._side = side
		self._pending_requests_lock = asyncio.Lock()

	
	async def start(self):
		self._logger.info(f"Starting IPCManager for {self._side}")
		asyncio.create_task(self._process_queue())
	
	async def _process_queue(self):
		while self._running:
			if self._in_queue.empty():
				await self._event.wait(timeout=1.0)
				await self._event.clear()
				continue
				
			msg: IPCMessage = self._in_queue.get_nowait()
			if msg.type == MessageType.RESPONSE:
				self._logger.info(f"Pending requests BEFORE handling response : {self._pending_requests}")
				if msg.id in self._pending_requests:
					future = self._pending_requests.pop(msg.id)
					future.set_result(msg.payload)
			elif msg.channel in self._handlers:
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
		await self._event.set()
	
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
		self._logger.info(f"Making request {request_id} on channel {channel}")
		future = asyncio.Future()
		async with self._pending_requests_lock:
			self._pending_requests[request_id] = future
			self._logger.info(f"Pending requests: {self._pending_requests}")
		self._out_queue.put(msg)
		await self._event.set()
		try:
			self._logger.info(f"[REQUEST] Waiting for response: {request_id}")
			result = await asyncio.wait_for(future, timeout)
			self._logger.info(f"[REQUEST] Got response: {request_id}")
			return result
		except asyncio.TimeoutError:
			self._logger.warning(f"Request {request_id} timed out after {timeout}s")
			async with self._pending_requests_lock:
				self._pending_requests.pop(request_id, None)
			raise
		except Exception as e:
			self._logger.error(f"[REQUEST] Error for {request_id}: {e}")
			async with self._pending_requests_lock:
				self._pending_requests.pop(request_id, None)
			raise


	async def respond(self, id: str, payload: Any):
		self._logger.info(f"Sending response for {id}")
		msg = IPCMessage(MessageType.RESPONSE, "", payload, id)
		self._out_queue.put(msg)
		await self._event.set()

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
		self._event._event.set()

	@classmethod
	def create_pair(cls) -> tuple["IPCManager", "IPCManager"]:
		in_queue = Queue()
		out_queue = Queue()
		event = Event()
		return (
			cls("panel", in_queue, out_queue, event),
			cls("bot", out_queue, in_queue, event)
		)