import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from multiprocessing import Queue
import uuid

from .async_ import Event


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
	id: str = datetime.now().isoformat()


class IPCManager:
	def __init__(self, in_queue: Optional[Queue] = None, out_queue: Optional[Queue] = None):
		self._in_queue = in_queue or Queue()
		self._out_queue = out_queue or Queue()
		self._handlers: dict[str, Callable[[int, Any], Coroutine]] = {}
		self._running = True
		self._pending_requests: dict[str, asyncio.Future] = {}
		self._event: Event = Event()
		
	async def start(self):
		asyncio.create_task(self._process_queue())
	
	async def _process_queue(self):
		while self._running:
			if self._in_queue.empty():
				await self._event.wait(timeout=1.0)
				await self._event.clear()
				continue
				
			msg: IPCMessage = self._in_queue.get_nowait()
			if msg.type == "response" and msg.id in self._pending_requests:
				future = self._pending_requests.pop(msg.id)
				future.set_result(msg.payload)
			elif msg.channel in self._handlers:
				if isinstance(msg.payload, dict):
					await self._handlers[msg.channel](msg.id, **msg.payload)
				else:
					await self._handlers[msg.channel](msg.id, msg.payload)

	async def send(self, channel: str, payload: Any = None):
		msg = IPCMessage("event", channel, payload)
		self._out_queue.put(msg)
		await self._event.set()
	
	async def request(self, channel: str, payload: Any = None) -> Any:
		request_id = str(uuid.uuid4())
		future = asyncio.Future()
		self._pending_requests[request_id] = future
		msg = IPCMessage("request", channel, payload, request_id)
		self._out_queue.put(msg)
		await self._event.set()
		return await future
	
	async def respond(self, id: str, payload: Any):
		msg = IPCMessage("response", "", payload, id)
		self._out_queue.put(msg)
		await self._event.set()
	

	def handle(self, channel: str):
		async def decorator(func: Callable[[Any], Coroutine]):
			self._handlers[channel] = func
			return func
		return decorator


	def stop(self):
		self._running = False
		self._event._event.set()

	@classmethod
	def create_pair(cls) -> tuple["IPCManager", "IPCManager"]:
		in_queue = Queue()
		out_queue = Queue()
		return (
			cls(in_queue, out_queue),
			cls(out_queue, in_queue)
		)