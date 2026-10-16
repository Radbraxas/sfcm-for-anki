# SPDX-License-Identifier: AGPL-3.0-or-later
"""JSON-RPC 2.0 over newline-delimited stdio, in the style of LSP (roadmap A07).

The Rust shell writes requests to our stdin and reads responses and notifications from
our stdout. Messages flow both ways: the engine can also ask the shell for things (for
example an API key from the OS keychain) with `call_shell`.

Logs go to stderr; stdout carries protocol messages only.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, BinaryIO

from pydantic import BaseModel, ValidationError

from .errors import EngineError, Reason, RpcCode
from .protocol import METHODS, ProgressParams, dump

log = logging.getLogger(__name__)

RequestId = str | int
Send = Callable[[dict[str, Any]], None]


@dataclass
class Context:
    """Passed to every handler: who is asking and how to report progress."""

    request_id: RequestId
    server: Server

    def progress(self, message: str, fraction: float | None = None) -> None:
        self.server.notify(
            "$/progress",
            dump(ProgressParams(request_id=self.request_id, message=message, fraction=fraction)),
        )

    async def call_shell(self, method: str, params: dict[str, Any]) -> Any:
        return await self.server.call_shell(method, params)


Handler = Callable[[Any, Context], Awaitable[BaseModel]]


@dataclass
class Server:
    send: Send
    handlers: dict[str, Handler] = field(default_factory=lambda: {})
    shell_timeout: float = 10.0
    _tasks: dict[RequestId, asyncio.Task[None]] = field(default_factory=lambda: {})
    _shell_calls: dict[str, asyncio.Future[Any]] = field(default_factory=lambda: {})
    _next_shell_id: int = 0

    def method(self, name: str) -> Callable[[Handler], Handler]:
        if name not in METHODS:
            raise KeyError(f"{name} is not declared in protocol.METHODS")

        def register(fn: Handler) -> Handler:
            self.handlers[name] = fn
            return fn

        return register

    # --- outgoing ------------------------------------------------------------

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def _reply(self, request_id: RequestId, result: Any) -> None:
        self.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _error(self, request_id: RequestId | None, error: dict[str, Any]) -> None:
        self.send({"jsonrpc": "2.0", "id": request_id, "error": error})

    async def call_shell(self, method: str, params: dict[str, Any]) -> Any:
        self._next_shell_id += 1
        call_id = f"e{self._next_shell_id}"
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._shell_calls[call_id] = future
        self.send({"jsonrpc": "2.0", "id": call_id, "method": method, "params": params})
        try:
            return await asyncio.wait_for(future, self.shell_timeout)
        except TimeoutError as exc:
            raise EngineError(Reason.SHELL_UNAVAILABLE, f"shell did not answer {method}") from exc
        finally:
            self._shell_calls.pop(call_id, None)

    # --- incoming ------------------------------------------------------------

    def handle_line(self, line: str | bytes) -> None:
        """Dispatch one raw line. Must be called from the event loop thread."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            self._error(None, {"code": int(RpcCode.PARSE_ERROR), "message": str(exc)})
            return
        if not isinstance(msg, dict):
            self._error(None, {"code": int(RpcCode.INVALID_REQUEST), "message": "not an object"})
            return
        self.handle_message(msg)  # pyright: ignore[reportUnknownArgumentType]

    def handle_message(self, msg: dict[str, Any]) -> None:
        method = msg.get("method")
        msg_id = msg.get("id")

        if method is None and msg_id is not None:
            self._resolve_shell_call(msg)
        elif method == "$/cancelRequest":
            params: dict[str, Any] = msg.get("params") or {}
            self.cancel(params.get("id"))
        elif isinstance(method, str) and msg_id is not None:
            task = asyncio.get_running_loop().create_task(
                self._run(msg_id, method, msg.get("params"))
            )
            self._tasks[msg_id] = task
            task.add_done_callback(lambda _t, i=msg_id: self._tasks.pop(i, None))
        elif isinstance(method, str):
            log.debug("ignoring notification %s", method)
        else:
            self._error(msg_id, {"code": int(RpcCode.INVALID_REQUEST), "message": "no method"})

    def cancel(self, request_id: RequestId | None) -> None:
        task = self._tasks.get(request_id) if request_id is not None else None
        if task is not None:
            task.cancel()

    def cancel_all(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()

    def _resolve_shell_call(self, msg: dict[str, Any]) -> None:
        future = self._shell_calls.get(str(msg["id"]))
        if future is None or future.done():
            return
        if "error" in msg:
            err: dict[str, Any] = msg["error"] or {}
            future.set_exception(
                EngineError(Reason.SHELL_UNAVAILABLE, str(err.get("message", "shell error")))
            )
        else:
            future.set_result(msg.get("result"))

    async def _run(self, request_id: RequestId, method: str, raw_params: Any) -> None:
        handler = self.handlers.get(method)
        if handler is None:
            self._error(
                request_id,
                {"code": int(RpcCode.METHOD_NOT_FOUND), "message": f"unknown method {method}"},
            )
            return
        params_model, _ = METHODS[method]
        try:
            params = params_model.model_validate(raw_params or {})
        except ValidationError as exc:
            self._error(
                request_id,
                {
                    "code": int(RpcCode.INVALID_PARAMS),
                    "message": "invalid params",
                    "data": {"errors": json.loads(exc.json(include_url=False))},
                },
            )
            return
        try:
            result = await handler(params, Context(request_id, self))
        except asyncio.CancelledError:
            self._error(
                request_id, {"code": int(RpcCode.REQUEST_CANCELLED), "message": "cancelled"}
            )
            return
        except EngineError as exc:
            self._error(request_id, exc.to_rpc())
            return
        except Exception as exc:
            log.exception("handler %s failed", method)
            self._error(request_id, {"code": int(RpcCode.INTERNAL_ERROR), "message": str(exc)})
            return
        self._reply(request_id, dump(result))


def stdout_sender(stream: BinaryIO) -> Send:
    lock = threading.Lock()

    def send(msg: dict[str, Any]) -> None:
        data = json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
        with lock:
            stream.write(data)
            stream.flush()

    return send


async def serve_stdio(server: Server, stdin: BinaryIO | None = None) -> None:
    """Read stdin until EOF. EOF means the shell went away, so we exit with it."""
    source = stdin or sys.stdin.buffer
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    # A thread keeps this portable: Windows pipes do not work with asyncio readers.
    def reader() -> None:
        for raw in iter(source.readline, b""):
            loop.call_soon_threadsafe(queue.put_nowait, raw)
        loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=reader, name="stdin-reader", daemon=True).start()
    while (line := await queue.get()) is not None:
        if line.strip():
            server.handle_line(line)
    server.cancel_all()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.sleep(0)
