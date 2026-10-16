# SPDX-License-Identifier: AGPL-3.0-or-later
"""USD prices per million tokens, for cost estimates shown to the user.

Anthropic first-party API rates as of 2026-10. Cache writes (5-minute TTL) cost 1.25x
input and cache reads 0.1x input. Unknown models (including every local model) return
None, and the UI shows "cost unknown" instead of a wrong number.
Update this table when prices change; it is not fetched at runtime.
"""

from __future__ import annotations

from ..protocol import Usage

# model -> (input, output)
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),  # prompts up to 100K tokens
    "claude-fable-5-1": (10.00, 50.00),
}


def estimate_cost(model: str, usage: Usage) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    input_rate, output_rate = price
    total = (
        usage.input_tokens * input_rate
        + usage.cache_write_tokens * input_rate * 1.25
        + usage.cache_read_tokens * input_rate * 0.10
        + usage.output_tokens * output_rate
    )
    return round(total / 1_000_000, 6)
