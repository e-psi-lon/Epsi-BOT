import asyncio
import uuid
import warnings
from collections.abc import Awaitable, Callable
from enum import Enum
from multiprocessing import Queue
from queue import Empty
from typing import Any, Concatenate, ParamSpec

from pydantic import BaseModel, Field

from epsi_bot.utils.loggers import get_logger
from epsi_bot.utils.type_utils import type_checking

__all__ = ["HandlerFunction", "IPCManager", "IPCMessage", "MessageType"]


class MessageType(Enum):
	EVENT = "event"
	DATA = "data"
	REQUEST = "request"
	RESPONSE = "response"


P = ParamSpec("P")
HandlerFunction = Callable[Concatenate[str, P], Awaitable[None]]

class IPCMessage(BaseModel):
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
	id: str = Field(default_factory=lambda: str(uuid.uuid4()))

	def validate(self) -> bool:
		"""Validate the IPCMessage structure"""
		return type_checking(
			self,
			IPCMessage,
			use_attrs=True,
			type=MessageType,
			channel=str,
			payload=Any | None,
			id=str,
		)


class IPCManager:
	def __init__(self, side: str, in_queue: Queue, out_queue: Queue):
		self._in_queue: Queue[IPCMessage] = in_queue
		self._out_queue: Queue[IPCMessage] = out_queue
		self._handlers: dict[str, HandlerFunction] = {}
		self._running = True
		self._logger = get_logger(f"IPC [{side}]")
		self._pending_requests: dict[str, asyncio.Future] = {}
		self._side = side
		self._reader_task: asyncio.Task | None = None
		self._pending_lock = asyncio.Lock()

	def _cancel_pending_request(self, request_id: str) -> asyncio.Future | None:
		"""Cancel a pending request and return the future if it was cancelled"""
		future = self._pending_requests.pop(request_id, None)
		if future and not future.done():
			future.cancel()
			self._logger.debug(f"Cancelled request {request_id}")
			return future
		return None

	async def start(self) -> None:
		self._logger.info(f"Starting IPCManager for {self._side}")
		self._reader_task = asyncio.create_task(
			asyncio.to_thread(self._sync_reader, asyncio.get_running_loop()),
			name=f"IPCManager-{self._side}",
		)

	def _sync_reader(self, loop: asyncio.AbstractEventLoop) -> None:
		try:
			while self._running:
				try:
					msg = self._in_queue.get(timeout=0.5)
					loop.call_soon_threadsafe(
						loop.create_task, self._handle_message(msg)
					)
				except Empty:
					continue
				except RuntimeError as e:
					self._logger.error(f"Event loop unavailable, stopping reader: {e}")
					break
		except Exception as e:  # noqa: BLE001
			self._logger.error(f"Fatal error in sync reader: {e}")
		finally:
			self._logger.debug("Sync reader task ended")

	async def _handle_message(self, message: IPCMessage) -> None:
		self._logger.debug(f"Received message: {message}")
		if not message.validate():
			self._logger.warning(f"Invalid IPCMessage received: {message}")
			return
		if message.type == MessageType.RESPONSE:
			async with self._pending_lock:
				self._logger.debug(f"Received response for {message.id}")
				pending_requests = self._pending_requests
				if message.id in pending_requests:
					self._logger.debug(f"Resolving future for {message.id}")
					future = pending_requests.pop(message.id)
					if not future.done():
						future.set_result(message.payload)
		elif message.channel in self._handlers:
			try:
				self._logger.debug(f"Handling message for {message.channel}")
				handler = self._handlers[message.channel]
				if isinstance(message.payload, dict):
					await handler(message.id, **message.payload)
				elif message.payload is None:
					await handler(message.id)
				else:
					await handler(message.id, message.payload)
			except Exception as e:  # noqa: BLE001 
				self._logger.error(f"Handler error for channel {message.channel}: {e}")
				if message.type == MessageType.REQUEST:
					await self.respond(message.id, {"error": str(e)})

	async def send(self, channel: str, payload: Any | None = None) -> None:
		msg = IPCMessage(MessageType.EVENT, channel, payload)
		self._logger.debug(f"Sending event: {msg}")
		self._out_queue.put(msg)

	async def request(
		self, channel: str, timeout: float = 5.0, **payload: Any | None
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
		except TimeoutError:
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
				# Raise a warning if a handler is already registered for the channel
				warnings.warn(
					f"Handler for channel '{channel}' is already registered. Be aware that this will overwrite the previous handler.",
					UserWarning,
				)
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
