# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio
import io
import json
import time

from sfcm_engine.errors import EngineError, Reason, RpcCode
from sfcm_engine.protocol import Empty, EngineInfo
from sfcm_engine.rpc import Context, Server, serve_stdio

from .conftest import Wire


def request(server: Server, method: str, params: object = None, id: int | str = 1) -> None:
    server.handle_line(json.dumps({"jsonrpc": "2.0", "id": id, "method": method, "params": params}))


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


async def test_unknown_method(server: Server, wire: Wire) -> None:
    request(server, "nope/nothing")
    await settle()
    assert wire.responses()[0]["error"]["code"] == RpcCode.METHOD_NOT_FOUND


async def test_parse_error(server: Server, wire: Wire) -> None:
    server.handle_line("{not json")
    assert wire.messages[0]["error"]["code"] == RpcCode.PARSE_ERROR


async def test_invalid_params(server: Server, wire: Wire) -> None:
    async def handler(_p: object, _c: Context) -> EngineInfo:
        raise AssertionError("must not run")

    server.method("cards/generate")(handler)
    request(server, "cards/generate", {"source": "", "count": 999})
    await settle()
    error = wire.responses()[0]["error"]
    assert error["code"] == RpcCode.INVALID_PARAMS
    assert {e["loc"][0] for e in error["data"]["errors"]} == {"source", "count"}


async def test_result_uses_camel_case(server: Server, wire: Wire) -> None:
    async def handler(_p: Empty, _c: Context) -> EngineInfo:
        return EngineInfo(
            engine_version="1",
            protocol_version=1,
            python_version="3",
            anki_version=None,
            data_dir="/x",
        )

    server.method("engine/info")(handler)
    request(server, "engine/info", {})
    await settle()
    assert wire.responses()[0]["result"]["engineVersion"] == "1"


async def test_app_error_carries_reason(server: Server, wire: Wire) -> None:
    async def handler(_p: Empty, _c: Context) -> EngineInfo:
        raise EngineError(Reason.MISSING_API_KEY, "no key", provider="anthropic")

    server.method("engine/info")(handler)
    request(server, "engine/info", {})
    await settle()
    error = wire.responses()[0]["error"]
    assert error["code"] == RpcCode.APP_ERROR
    assert error["data"] == {"reason": "missing_api_key", "provider": "anthropic"}


async def test_cancel_stops_handler_within_a_second(server: Server, wire: Wire) -> None:
    started = asyncio.Event()

    async def slow(_p: Empty, ctx: Context) -> EngineInfo:
        ctx.progress("calling_provider", 0.1)
        started.set()
        await asyncio.sleep(60)
        raise AssertionError("not cancelled")

    server.method("engine/info")(slow)
    request(server, "engine/info", {}, id="req-7")
    await started.wait()
    t0 = time.monotonic()
    server.handle_line(
        json.dumps({"jsonrpc": "2.0", "method": "$/cancelRequest", "params": {"id": "req-7"}})
    )
    while not wire.responses():
        await asyncio.sleep(0.01)
    assert time.monotonic() - t0 < 1.0
    assert wire.responses()[0]["error"]["code"] == RpcCode.REQUEST_CANCELLED
    progress = wire.notifications("$/progress")[0]["params"]
    assert progress == {"requestId": "req-7", "message": "calling_provider", "fraction": 0.1}


async def test_shell_call_round_trip(server: Server, wire: Wire) -> None:
    async def handler(_p: Empty, ctx: Context) -> EngineInfo:
        result = await ctx.call_shell("secrets/get", {"service": "anthropic"})
        return EngineInfo(
            engine_version=result["value"],
            protocol_version=1,
            python_version="",
            anki_version=None,
            data_dir="",
        )

    server.method("engine/info")(handler)
    request(server, "engine/info", {})
    await settle()
    outgoing = next(m for m in wire.messages if m.get("method") == "secrets/get")
    server.handle_line(
        json.dumps({"jsonrpc": "2.0", "id": outgoing["id"], "result": {"value": "k"}})
    )
    await settle()
    assert wire.responses()[-1]["result"]["engineVersion"] == "k"


async def test_shell_call_times_out(server: Server, wire: Wire) -> None:
    async def handler(_p: Empty, ctx: Context) -> EngineInfo:
        await ctx.call_shell("secrets/get", {"service": "anthropic"})
        raise AssertionError("unreachable")

    server.method("engine/info")(handler)
    request(server, "engine/info", {})
    while not wire.responses():
        await asyncio.sleep(0.05)
    assert wire.responses()[0]["error"]["data"]["reason"] == "shell_unavailable"


async def test_serve_stdio_exits_on_eof(server: Server, wire: Wire) -> None:
    async def handler(_p: Empty, _c: Context) -> EngineInfo:
        return EngineInfo(
            engine_version="1",
            protocol_version=1,
            python_version="",
            anki_version=None,
            data_dir="",
        )

    server.method("engine/info")(handler)
    stdin = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"engine/info","params":{}}\n')
    await asyncio.wait_for(serve_stdio(server, stdin), timeout=2)
