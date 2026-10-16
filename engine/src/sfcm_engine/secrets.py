# SPDX-License-Identifier: AGPL-3.0-or-later
"""Where API keys come from (roadmap A08).

Inside the app, keys live in the OS keychain, which only the Rust shell touches; the
engine asks for one when it needs it and keeps it in memory for that call only.
Headless runs (CLI, evals, CI) read the provider's usual environment variable instead.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from .redaction import register_secret

ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class KeySource(Protocol):
    async def get(self, service: str) -> str | None: ...


class EnvKeySource:
    async def get(self, service: str) -> str | None:
        var = ENV_VARS.get(service)
        value = os.environ.get(var) if var else None
        register_secret(value)
        return value or None


class ShellKeySource:
    """Asks the Rust shell, which reads the OS keychain."""

    def __init__(self, call_shell: Callable[[str, dict[str, Any]], Awaitable[Any]]) -> None:
        self._call_shell = call_shell

    async def get(self, service: str) -> str | None:
        result = await self._call_shell("secrets/get", {"service": service})
        value: Any = cast(dict[str, Any], result).get("value") if isinstance(result, dict) else None
        if not isinstance(value, str) or not value:
            return None
        register_secret(value)
        return value
