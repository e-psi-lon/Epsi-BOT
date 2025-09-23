import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing import Queue
from queue import Empty
from typing import Any, Awaitable, Callable, Optional, Concatenate, ParamSpec

from epsi_bot.utils.type_utils import type_checking
from epsi_bot.utils.loggers import get_logger

__all__ = ["IPCMessage", "IPCManager", "MessageType", "HandlerFunction"]


class MessageType(Enum):
	EVENT = "event"
	DATA = "data"
	REQUEST = "request"
	RESPONSE = "response"


P = ParamSpec("P")
HandlerFunction = Callable[Concatenate[str, P], Awaitable[None]]


@dataclass(slots=True, frozen=True)
class IPCMessage:
	"""
	Represents a message in the IPC system.

	Attributes
	----------
	type: MessageType
	        The type of the message (event, data, request, response).
	channel: str
	        The channel the message is sent on.
	payload: dict[str, Any] | Any | None
	        The payload of the message, that can be a dictionary (with string keys) or any other type. May be None.
	id: str
	        A unique identifier for the message, generated if not provided.

	"""

	type: MessageType
	channel: str
	payload: dict[str, Any] | Any | None
	id: str = field(default_factory=lambda: str(uuid.uuid4()))

	def validate(self) -> bool:
		"""Validate the IPCMessage structure"""
		return type_checking(
			self,
			IPCMessage,
			use_attrs=True,
			type=MessageType,
			channel=str,
			payload=Optional[Any],
			id=str,
		)


class IPCManager:
	def __init__(self, side: str, in_queue: Queue, out_queue: Queue):
		self._in_queue: Queue[IPCMessage] = in_queue
		self._async_in_queue: asyncio.Queue[IPCMessage] = asyncio.Queue()
		self._out_queue: Queue[IPCMessage] = out_queue
		# noinspection PyTypeHints
		self._handlers: dict[str, HandlerFunction] = {}
		self._running = True
		self._logger = get_logger(f"IPC [{side}]")
		self._pending_requests: dict[str, asyncio.Future] = {}
		self._side = side
		self._reader_task: Optional[asyncio.Task] = None
		self._processor_task: Optional[asyncio.Task] = None
		self._pending_lock = asyncio.Lock()

	def _cancel_pending_request(self, request_id: str) -> Optional[asyncio.Future]:
		"""Cancel a pending request and return the future if it was cancelled"""
		future = self._pending_requests.pop(request_id, None)
		if future and not future.done():
			future.cancel()
			self._logger.debug(f"Cancelled request {request_id}")
			return future
		return None

	async def start(self) -> None:
		self._logger.info(f"Starting IPCManager for {self._side}")
		self._processor_task = asyncio.create_task(self._process_queue())
		self._reader_task = asyncio.create_task(
			asyncio.to_thread(self._sync_reader, asyncio.get_event_loop()),
			name=f"IPCManager-{self._side}",
		)

	def _sync_reader(self, loop: asyncio.AbstractEventLoop) -> None:
		try:
			while self._running:
				try:
					msg = self._in_queue.get(timeout=0.5)
					loop.call_soon_threadsafe(self._async_in_queue.put_nowait, msg)
				except Empty:
					continue
				except Exception as e:
					self._logger.error(f"Error in sync reader: {e}")
					break
		except Exception as e:
			self._logger.error(f"Fatal error in sync reader: {e}")
		finally:
			self._logger.debug("Sync reader task ended")

	async def _process_queue(self) -> None:
		try:
			while self._running:
				try:
					msg = await self._async_in_queue.get()
					self._logger.debug(f"Received message: {msg}")
					if not msg.validate():
						self._logger.warning(f"Invalid IPCMessage received: {msg}")
						continue
					if msg.type == MessageType.RESPONSE:
						async with self._pending_lock:
							self._logger.debug(f"Received response for {msg.id}")
							pending_requests = self._pending_requests
							if msg.id in pending_requests:
								self._logger.debug(f"Resolving future for {msg.id}")
								future = pending_requests.pop(msg.id)
								if not future.done():
									future.set_result(msg.payload)
					elif msg.channel in self._handlers:
						try:
							self._logger.debug(f"Handling message for {msg.channel}")
							if isinstance(msg.payload, dict):
								await self._handlers[msg.channel](msg.id, **msg.payload)
							elif msg.payload is None:
								await self._handlers[msg.channel](msg.id)
							else:
								await self._handlers[msg.channel](msg.id, msg.payload)
						except Exception as e:
							self._logger.error(
								f"Handler error for channel {msg.channel}: {e}"
							)
							if msg.type == MessageType.REQUEST:
								await self.respond(msg.id, {"error": str(e)})
				except asyncio.CancelledError:
					self._logger.debug("Queue processor cancelled")
					break
				except Exception as e:
					self._logger.error(f"Error processing message: {e}")
		finally:
			self._logger.debug("Queue processor ended")

	async def send(self, channel: str, payload: Any | None = None) -> None:
		msg = IPCMessage(MessageType.EVENT, channel, payload)
		self._logger.debug(f"Sending event: {msg}")
		self._out_queue.put(msg)

	async def request(
		self, channel: str, timeout: float = 5.0, **payload: Optional[Any]
	) -> Any:
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
		final_payload: dict[str, Any] | Any | None = payload
		if not payload:
			final_payload = None
		elif len(payload) == 1:
			final_payload = next(iter(payload.values()))
		msg = IPCMessage(MessageType.REQUEST, channel, final_payload)
		request_id = msg.id
		future: asyncio.Future = asyncio.Future()
		async with self._pending_lock:
			self._pending_requests[request_id] = future
		self._logger.debug(f"Sending request with id {request_id}")
		self._out_queue.put(msg)
		try:
			return await asyncio.wait_for(future, timeout)
		except asyncio.TimeoutError:
			self._logger.warning(f"Request {request_id} timed out after {timeout}s")
			async with self._pending_lock:
				self._cancel_pending_request(request_id)
			raise
		except Exception as e:
			self._logger.error(f"Error for {request_id}: {e}")
			async with self._pending_lock:
				self._cancel_pending_request(request_id)
			raise

	async def respond(self, request_id: str, payload: Any) -> None:
		self._logger.debug(f"Sending response for {request_id}")
		msg = IPCMessage(MessageType.RESPONSE, "", payload, request_id)
		self._out_queue.put(msg)

	def handle(self, channel: str) -> Callable[[HandlerFunction], HandlerFunction]:
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

		def decorator(func: HandlerFunction) -> HandlerFunction:
			if channel in self._handlers:
				self._logger.warning(f"Overwriting handler for channel {channel}")
			self._handlers[channel] = func
			return func

		return decorator

	async def stop(self) -> None:
		self._logger.info("Stopping IPCManager")
		self._running = False

		# Cancel all pending requests
		async with self._pending_lock:
			for request_id in list(self._pending_requests.keys()):
				self._cancel_pending_request(request_id)
			self._pending_requests.clear()
		if self._processor_task and not self._processor_task.done():
			self._processor_task.cancel()
			try:
				await self._processor_task
			except asyncio.CancelledError:
				pass

		if self._reader_task and not self._reader_task.done():
			self._reader_task.cancel()
			try:
				await self._reader_task
			except asyncio.CancelledError:
				pass

	async def cancel_request(self, request_id: str) -> bool:
		async with self._pending_lock:
			return self._cancel_pending_request(request_id) is not None

	@classmethod
	def create_pair(cls) -> tuple["IPCManager", "IPCManager"]:
		in_queue: Queue[IPCMessage] = Queue()
		out_queue: Queue[IPCMessage] = Queue()
		return (cls("panel", in_queue, out_queue), cls("bot", out_queue, in_queue))
