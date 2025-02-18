import asyncio
import uuid
import enum
from dataclasses import dataclass
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from typing import Any, Coroutine, Optional, Callable, Dict

from .loggers import get_logger
# --- Message Format Definitions ---

class MessageType(enum.Enum):
    EVENT = "event"
    REQUEST = "request"
    RESPONSE = "response"

@dataclass
class IPCMessage:
    type: MessageType
    command: Optional[str] = None
    payload: Any = None
    request_id: Optional[str] = None

# Type alias for asynchronous handler functions.
HandlerType = Callable[[Any], Coroutine[Any, Any, Any]]


class AsyncIPC:
    def __init__(self, connection, side: str = "unknown") -> None:
        """
        connection: a multiprocessing connection object (one end of a Pipe).
        side: A string indicating the side ('parent' or 'child') for logging.
        """
        self.connection: Connection = connection
        self.side = side
        self.loop: asyncio.AbstractEventLoop = None
        self.handlers: Dict[str, HandlerType] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.logger = get_logger(f"ipc-{side}")
        self.logger.debug("Initializing AsyncIPC on side '%s'", side)

    async def start(self):
        self.loop = asyncio.new_event_loop()
        self._receiver_task = self.loop.run_in_executor(None, self._receive_loop())

    @classmethod
    def create_ipc_pair(cls, parent_side: str = "panel", child_side: str = "bot") -> "tuple[AsyncIPC, AsyncIPC]":
        """
        Creates a duplex Pipe and returns a pair of AsyncIPC instances.
        In a multiprocess scenario, one process would receive one of these objects.
        """
        parent_conn, child_conn = Pipe(duplex=True)
        ipc_parent = cls(parent_conn, side=parent_side)
        ipc_child = cls(child_conn, side=child_side)
        return ipc_parent, ipc_child

    def handler(self, command: str):
        """
        Decorator to register an asynchronous handler for a specific command.
        The handler should be a coroutine function accepting a payload.
        """
        def decorator(func: HandlerType) -> HandlerType:
            self.handlers[command] = func
            self.logger.debug("Registered handler for command '%s'", command)
            return func
        return decorator

    async def send_event(self, command: str, payload: Any) -> None:
        """
        Asynchronously sends an event message (fire and forget).
        """
        msg = IPCMessage(
            type=MessageType.EVENT,
            command=command,
            payload=payload,
        )
        self.logger.debug("Sending event: %s", msg)
        await self.loop.run_in_executor(None, self.connection.send, msg)

    async def send_request(self, command: str, payload: Any, timeout: Optional[float] = 5.0) -> Any:
        """
        Sends a request message and waits for a response.
        Raises asyncio.TimeoutError if the response is not received within the timeout.
        """
        request_id = str(uuid.uuid4())
        msg = IPCMessage(
            type=MessageType.REQUEST,
            command=command,
            payload=payload,
            request_id=request_id,
        )
        future = self.loop.create_future()
        self.pending_requests[request_id] = future
        self.logger.debug("Sending request: %s", msg)
        await self.loop.run_in_executor(None, self.connection.send, msg)
        try:
            response = await asyncio.wait_for(future, timeout)
            self.logger.debug("Received response for request %s: %s", request_id, response)
            return response
        except asyncio.TimeoutError:
            self.logger.error("Request timed out: %s", request_id)
            self.pending_requests.pop(request_id, None)
            raise
        except asyncio.CancelledError:
            self.logger.error("Request cancelled: %s", request_id)
            self.pending_requests.pop(request_id, None)
            raise

    async def send_response(self, request_id: str, payload: Any) -> None:
        """
        Sends a response message for the given request_id.
        """
        msg = IPCMessage(
            type=MessageType.RESPONSE,
            payload=payload,
            request_id=request_id,
        )
        self.logger.debug("Sending response for request %s: %s", request_id, msg)
        await self.loop.run_in_executor(None, self.connection.send, msg)

    async def _receive_loop(self) -> None:
        """
        Internal loop that continuously receives IPCMessage instances and dispatches them.
        """
        while True:
            try:
                msg: IPCMessage = await self.loop.run_in_executor(None, self.connection.recv)
            except EOFError:
                self.logger.warning("Connection closed (EOF). Exiting receive loop.")
                break
            except Exception as e:
                self.logger.error("Error receiving message: %s", e)
                continue

            self.logger.debug("Received message: %s", msg)
            if msg.type == MessageType.EVENT:
                command = msg.command
                payload = msg.payload
                handler = self.handlers.get(command)
                if handler:
                    self.loop.create_task(self._safe_handler_call(handler, payload))
                else:
                    self.logger.warning("No handler registered for event command '%s'", command)
            elif msg.type == MessageType.REQUEST:
                command = msg.command
                payload = msg.payload
                request_id = msg.request_id
                handler = self.handlers.get(command)
                if handler:
                    async def process_request():
                        try:
                            result: Any
                            if payload is None:
                                result = await handler()
                            elif isinstance(payload, dict):
                                result = await handler(**payload)
                            else:
                                result = await handler(payload)
                            
                            await self.send_response(request_id, result)
                        except Exception as e:
                            self.logger.error("Error processing request '%s': %s", command, e)
                            await self.send_response(request_id, {"error": str(e)})
                    self.loop.create_task(process_request())
                else:
                    self.logger.warning("No handler registered for request command '%s'", command)
                    await self.send_response(request_id, {"error": f"No handler for command '{command}'"})
            elif msg.type == MessageType.RESPONSE:
                request_id = msg.request_id
                payload = msg.payload
                future = self.pending_requests.pop(request_id, None)
                if future:
                    if not future.cancelled():
                        future.set_result(payload)
                    else:
                        self.logger.warning("Future for request %s was cancelled", request_id)
                else:
                    self.logger.warning("No pending request for response %s", request_id)
            else:
                self.logger.error("Unknown message type: %s", msg.type)

    async def _safe_handler_call(self, handler: HandlerType, payload: Any) -> None:
        """
        Helper to call a handler with proper exception handling.
        """
        try:
            await handler(payload)
        except Exception as e:
            self.logger.error("Exception in handler: %s", e)

    async def close(self):
        """
        Clean up: cancel the receiver task and close the connection.
        """
        self.logger.debug("Closing IPC on side '%s'", self.side)
        self._receiver_task.cancel()
        try:
            await self._receiver_task
        except asyncio.CancelledError:
            pass
        self.connection.close()
        for req_id, fut in self.pending_requests.items():
            if not fut.done():
                fut.cancel()
        self.pending_requests.clear()
