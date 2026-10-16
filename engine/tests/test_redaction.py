# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import logging
import sys

import pytest

from sfcm_engine.redaction import MASK, RedactingFormatter, redact, register_secret


def test_registered_secret_is_masked() -> None:
    register_secret("my-very-private-key-123")
    assert redact("key=my-very-private-key-123 used") == f"key={MASK} used"


@pytest.mark.parametrize(
    "text",
    [
        "sk-ant-api03-AbCdEf0123456789xyz",
        "sk-proj-0123456789abcdefghijKLMN",
        "Authorization: Bearer abcdefghijklmnop0123",
        '{"x-api-key": "abcdefghijklmnop0123"}',
    ],
)
def test_key_shapes_are_masked(text: str) -> None:
    assert MASK in redact(text)
    assert "0123" not in redact(text)


def test_formatter_redacts_tracebacks() -> None:
    register_secret("traceback-secret-value")
    try:
        raise RuntimeError("failed with traceback-secret-value")
    except RuntimeError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    out = RedactingFormatter("%(message)s").format(record)
    assert "traceback-secret-value" not in out
