# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAI and OpenAI-compatible endpoints (Ollama, LM Studio), via the `openai` SDK.

Local servers vary in how well they honour JSON Schema, so a reply that fails
validation gets one repair attempt with the validation error fed back.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import openai
from pydantic import BaseModel, ValidationError

from ..errors import EngineError, Reason
from ..protocol import ProviderId, Usage
from .base import (
    Location,
    StructuredRequest,
    StructuredResult,
    is_local_url,
    parse_json_output,
    strict_json_schema,
)
from .pricing import estimate_cost

ClientFactory = Callable[[str, str | None], Any]


def _default_client(api_key: str, base_url: str | None) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=2, timeout=600.0)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        id: ProviderId,
        name: str,
        default_model: str,
        base_url: str | None,
        needs_api_key: bool,
        client_factory: ClientFactory = _default_client,
    ) -> None:
        self.id: ProviderId = id
        self.name = name
        self.default_model = default_model
        self.base_url = base_url
        self.needs_api_key = needs_api_key
        self.location: Location = "local" if is_local_url(base_url) else "cloud"
        self._client_factory = client_factory

    async def generate[M: BaseModel](
        self, request: StructuredRequest, output: type[M], api_key: str | None
    ) -> StructuredResult[M]:
        if self.needs_api_key and not api_key:
            raise EngineError(Reason.MISSING_API_KEY, f"no {self.name} API key", provider=self.id)
        # Local servers ignore the key, but the SDK requires a non-empty one.
        client = self._client_factory(api_key or "not-needed", self.base_url)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": output.__name__,
                "schema": strict_json_schema(output),
                "strict": True,
            },
        }
        usage = Usage()
        last_error: Exception | None = None
        for _attempt in range(2):
            completion = await self._call(client, request, messages, response_format)
            if completion.usage:
                usage.input_tokens += completion.usage.prompt_tokens or 0
                usage.output_tokens += completion.usage.completion_tokens or 0
            choice = completion.choices[0]
            if choice.finish_reason == "length":
                raise EngineError(Reason.OUTPUT_TRUNCATED, "reply hit max_tokens")
            text = choice.message.content or ""
            try:
                value = parse_json_output(text, output)
            except (ValueError, ValidationError) as exc:
                last_error = exc
                messages += [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": "That reply did not match the required JSON schema: "
                        f"{exc}. Reply again with only the corrected JSON.",
                    },
                ]
                continue
            usage.cost_usd = estimate_cost(completion.model, usage)
            return StructuredResult(
                value=value, usage=usage, model=completion.model or request.model
            )
        raise EngineError(Reason.INVALID_OUTPUT, str(last_error), provider=self.id)

    async def _call(
        self,
        client: Any,
        request: StructuredRequest,
        messages: list[dict[str, str]],
        response_format: dict[str, Any],
    ) -> Any:
        try:
            return await client.chat.completions.create(
                model=request.model,
                messages=messages,
                response_format=response_format,
                max_completion_tokens=request.max_tokens,
            )
        except openai.AuthenticationError as exc:
            raise EngineError(Reason.PROVIDER_AUTH, exc.message, provider=self.id) from exc
        except openai.NotFoundError as exc:
            raise EngineError(
                Reason.MODEL_NOT_FOUND, exc.message, provider=self.id, model=request.model
            ) from exc
        except openai.RateLimitError as exc:
            raise EngineError(Reason.PROVIDER_RATE_LIMITED, exc.message, provider=self.id) from exc
        except openai.BadRequestError as exc:
            raise EngineError(Reason.PROVIDER_BAD_REQUEST, exc.message, provider=self.id) from exc
        except (openai.APIStatusError, openai.APIConnectionError) as exc:
            raise EngineError(Reason.PROVIDER_UNAVAILABLE, str(exc), provider=self.id) from exc
