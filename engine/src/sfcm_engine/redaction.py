# SPDX-License-Identifier: AGPL-3.0-or-later
"""Keep secrets out of logs (roadmap A08).

Two layers: every key the engine receives is registered and masked verbatim, and
well-known key shapes are masked by pattern in case one slips in some other way.
"""

from __future__ import annotations

import logging
import re
import threading

MASK = "[REDACTED]"

_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),  # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),  # OpenAI
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(x-api-key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._\-]{16,}"),
]

_lock = threading.Lock()
_known: set[str] = set()


def register_secret(value: str | None) -> None:
    if value and len(value) >= 8:
        with _lock:
            _known.add(value)


def redact(text: str) -> str:
    with _lock:
        known = sorted(_known, key=len, reverse=True)
    for secret in known:
        text = text.replace(secret, MASK)
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.groups() else "") + MASK, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Formats normally, then redacts the whole line, tracebacks included."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()  # stderr: stdout belongs to the protocol
    handler.setFormatter(RedactingFormatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # SDK debug logs can include request headers; keep them at WARNING.
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
