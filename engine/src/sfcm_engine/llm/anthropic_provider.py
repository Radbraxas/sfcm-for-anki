# SPDX-License-Identifier: AGPL-3.0-or-later
"""Anthropic adapter, using the official `anthropic` SDK.

- Structured output through `output_config.format` (JSON Schema), so replies always
  parse; current models reject forced tool choice, so tools are not used for this.
- The system prompt (rubric + instructions) is marked for prompt caching; it is the
  same for every call, while the source text goes in the user message.
- Models that support it get server-side refusal fallbacks (`fallbacks: "default"`).
- Thinking is left at the model default; depth is controlled with `effort`.

Large jobs will move to the Message Batches API with the job runner (roadmap D12).
Batches reject `fallbacks`, so that path will omit it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from ..errors import EngineError, Reason
from ..protocol import ProviderId, Usage
from .base import Location, StructuredRequest, StructuredResult, strict_json_schema
from .pricing import estimate_cost

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that accept `fallbacks: "default"` on the Claude API.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-5"}

ClientFactory = Callable[[str], Any]


def _default_client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=600.0)


class AnthropicProvider:
    id: ProviderId = "anthropic"
    name = "Anthropic Claude"
    location: Location = "cloud"
    needs_api_key = True
    default_model = "claude-opus-5-5"
    base_url: str | None = None

    def __init__(self, client_factory: ClientFactory = _default_client) -> None:
        self._client_factory = client_factory

    def build_params(self, request: StructuredRequest, output: type[BaseModel]) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "system": [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": [{"role": "user", "content": request.user}],
            "output_config": {
                "effort": request.effort,
                "format": {"type": "json_schema", "schema": strict_json_schema(output)},
            },
        }
        if request.model in FALLBACK_MODELS:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    async def generate[M: BaseModel](
        self, request: StructuredRequest, output: type[M], api_key: str | None
    ) -> StructuredResult[M]:
        if not api_key:
            raise EngineError(Reason.MISSING_API_KEY, "no Anthropic API key", provider=self.id)
        client = self._client_factory(api_key)
        params = self.build_params(request, output)
        try:
            if "betas" in params:
                response = await client.beta.messages.create(**params)
            else:
                response = await client.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise EngineError(Reason.PROVIDER_AUTH, exc.message, provider=self.id) from exc
        except anthropic.PermissionDeniedError as exc:
            raise EngineError(Reason.PROVIDER_AUTH, exc.message, provider=self.id) from exc
        except anthropic.NotFoundError as exc:
            raise EngineError(
                Reason.MODEL_NOT_FOUND, exc.message, provider=self.id, model=request.model
            ) from exc
        except anthropic.RateLimitError as exc:
            retry_after = exc.response.headers.get("retry-after")
            raise EngineError(
                Reason.PROVIDER_RATE_LIMITED, exc.message, provider=self.id, retryAfter=retry_after
            ) from exc
        except anthropic.BadRequestError as exc:
            raise EngineError(Reason.PROVIDER_BAD_REQUEST, exc.message, provider=self.id) from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise EngineError(Reason.PROVIDER_UNAVAILABLE, str(exc), provider=self.id) from exc

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise EngineError(
                Reason.REFUSED, "the model declined this input", provider=self.id, category=category
            )
        if response.stop_reason == "max_tokens":
            raise EngineError(Reason.OUTPUT_TRUNCATED, "reply hit max_tokens; ask for fewer cards")

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            value = output.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise EngineError(Reason.INVALID_OUTPUT, str(exc), provider=self.id) from exc

        u = response.usage
        usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", None) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", None) or 0,
        )
        usage.cost_usd = estimate_cost(response.model, usage)
        return StructuredResult(value=value, usage=usage, model=response.model)
