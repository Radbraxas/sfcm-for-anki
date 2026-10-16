# SPDX-License-Identifier: AGPL-3.0-or-later
"""The provider interface every LLM adapter implements.

The engine only ever asks for one thing: "given this system prompt and user message,
return an instance of this pydantic model". Adapters own the provider-specific way of
getting reliable structured output, error mapping and cost accounting.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel

from ..protocol import Effort, ProviderId, Usage

T = TypeVar("T", bound=BaseModel)

Location = Literal["cloud", "local"]


@dataclass(frozen=True)
class StructuredRequest:
    system: str  # stable across calls so it can be prompt-cached
    user: str  # the volatile part: source text, options
    model: str
    effort: Effort = "high"
    max_tokens: int = 16_000


@dataclass(frozen=True)
class StructuredResult[M: BaseModel]:
    value: M
    usage: Usage
    model: str  # the model that actually answered (may differ after a fallback)


class Provider(Protocol):
    id: ProviderId
    name: str
    location: Location
    needs_api_key: bool
    default_model: str
    base_url: str | None

    async def generate[M: BaseModel](
        self, request: StructuredRequest, output: type[M], api_key: str | None
    ) -> StructuredResult[M]: ...


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for structured output: every property required, no extra keys.

    Pydantic omits fields with defaults from `required`; structured-output APIs want
    them all listed, and `additionalProperties: false` on every object.
    """
    schema = model.model_json_schema(by_alias=True, mode="serialization")

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:  # pyright: ignore[reportUnknownMemberType]
                node["required"] = list(node["properties"])  # pyright: ignore[reportUnknownArgumentType]
                node["additionalProperties"] = False
            for child in node.values():  # pyright: ignore[reportUnknownVariableType]
                visit(child)
        elif isinstance(node, list):
            for child in node:  # pyright: ignore[reportUnknownVariableType]
                visit(child)

    visit(schema)
    schema.pop("title", None)
    return schema


def is_local_url(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")


def parse_json_output[M: BaseModel](text: str, output: type[M]) -> M:
    """Parse a model's JSON reply, tolerating a Markdown fence around it."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        stripped = stripped.rsplit("```", 1)[0]
    return output.model_validate(json.loads(stripped))
