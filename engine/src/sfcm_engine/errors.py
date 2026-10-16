# SPDX-License-Identifier: AGPL-3.0-or-later
"""Error codes shared by every layer of the engine.

JSON-RPC errors carry a numeric `code` and, in `data.reason`, a stable string the UI
translates. The engine never returns display text meant for end users.
"""

from enum import IntEnum, StrEnum
from typing import Any


class RpcCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    REQUEST_CANCELLED = -32800  # same value LSP uses
    APP_ERROR = -32000


class Reason(StrEnum):
    """Stable, translatable reasons for APP_ERROR responses."""

    MISSING_API_KEY = "missing_api_key"
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_BAD_REQUEST = "provider_bad_request"
    MODEL_NOT_FOUND = "model_not_found"
    LOCAL_ONLY_BLOCKED = "local_only_blocked"
    UNKNOWN_PROVIDER = "unknown_provider"
    INVALID_OUTPUT = "invalid_output"
    OUTPUT_TRUNCATED = "output_truncated"
    REFUSED = "refused"
    SHELL_UNAVAILABLE = "shell_unavailable"


class EngineError(Exception):
    """An error that is reported to the caller as a JSON-RPC APP_ERROR."""

    def __init__(self, reason: Reason, message: str, **details: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details

    def to_rpc(self) -> dict[str, Any]:
        return {
            "code": int(RpcCode.APP_ERROR),
            "message": self.message,
            "data": {"reason": str(self.reason), **self.details},
        }
