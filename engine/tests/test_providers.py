# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from sfcm_engine.cards import GeneratedCardBatch
from sfcm_engine.errors import EngineError, Reason
from sfcm_engine.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from sfcm_engine.llm.base import StructuredRequest, strict_json_schema
from sfcm_engine.llm.openai_compat import OpenAICompatibleProvider

from .conftest import card

BATCH_JSON = json.dumps(GeneratedCardBatch(cards=[card()]).model_dump(by_alias=True))


class FakeMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def anthropic_response(
    text: str = BATCH_JSON, stop_reason: str = "end_turn", model: str = "claude-opus-5-5"
) -> Any:
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=2000,
            cache_creation_input_tokens=0,
        ),
    )


def fake_anthropic(response: Any) -> tuple[AnthropicProvider, FakeMessages, FakeMessages]:
    beta, plain = FakeMessages(response), FakeMessages(response)
    client = SimpleNamespace(beta=SimpleNamespace(messages=beta), messages=plain)
    return AnthropicProvider(client_factory=lambda _key: client), beta, plain


def req(model: str = "claude-opus-5-5") -> StructuredRequest:
    return StructuredRequest(system="SYSTEM", user="USER", model=model)


def test_strict_schema_requires_every_field() -> None:
    schema = strict_json_schema(GeneratedCardBatch)
    card_def = schema["$defs"]["GeneratedCard"]
    assert card_def["additionalProperties"] is False
    assert set(card_def["required"]) == set(card_def["properties"])
    assert "noteType" in card_def["properties"]


async def test_anthropic_request_shape_with_fallbacks() -> None:
    provider, beta, plain = fake_anthropic(anthropic_response())
    result = await provider.generate(req(), GeneratedCardBatch, "sk-ant-test")
    assert plain.calls == []
    call = beta.calls[0]
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["messages"] == [{"role": "user", "content": "USER"}]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "high"
    assert "thinking" not in call and "tool_choice" not in call
    assert len(result.value.cards) == 1
    # 1000*4 + 2000*0.4 + 500*20 per million
    assert result.usage.cost_usd == pytest.approx((4000 + 800 + 10000) / 1e6)


async def test_haiku_skips_fallbacks() -> None:
    provider, beta, plain = fake_anthropic(anthropic_response(model="claude-haiku-5-5"))
    await provider.generate(req("claude-haiku-5-5"), GeneratedCardBatch, "k")
    assert beta.calls == [] and "fallbacks" not in plain.calls[0]


@pytest.mark.parametrize(
    ("stop_reason", "reason"),
    [("refusal", Reason.REFUSED), ("max_tokens", Reason.OUTPUT_TRUNCATED)],
)
async def test_anthropic_stop_reasons(stop_reason: str, reason: Reason) -> None:
    provider, _, _ = fake_anthropic(anthropic_response(stop_reason=stop_reason))
    with pytest.raises(EngineError) as info:
        await provider.generate(req(), GeneratedCardBatch, "k")
    assert info.value.reason == reason


async def test_anthropic_requires_key() -> None:
    provider, _, _ = fake_anthropic(anthropic_response())
    with pytest.raises(EngineError) as info:
        await provider.generate(req(), GeneratedCardBatch, None)
    assert info.value.reason == Reason.MISSING_API_KEY


def openai_completion(text: str) -> Any:
    return SimpleNamespace(
        model="llama3.1:8b",
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text))],
    )


class FakeChat:
    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return openai_completion(self.replies[len(self.calls) - 1])


def fake_ollama(replies: list[str]) -> tuple[OpenAICompatibleProvider, FakeChat]:
    chat = FakeChat(replies)
    client = SimpleNamespace(chat=SimpleNamespace(completions=chat))
    provider = OpenAICompatibleProvider(
        id="ollama",
        name="Ollama",
        default_model="llama3.1:8b",
        base_url="http://localhost:11434/v1",
        needs_api_key=False,
        client_factory=lambda _k, _u: client,
    )
    return provider, chat


async def test_local_provider_repairs_once() -> None:
    provider, chat = fake_ollama(["not json at all", f"```json\n{BATCH_JSON}\n```"])
    result = await provider.generate(req("llama3.1:8b"), GeneratedCardBatch, None)
    assert provider.location == "local"
    assert len(chat.calls) == 2
    assert "did not match" in chat.calls[1]["messages"][-1]["content"]
    assert result.usage.input_tokens == 20
    assert result.usage.cost_usd is None  # unknown local model


async def test_local_provider_gives_up_after_repair() -> None:
    provider, _ = fake_ollama(["nope", "still nope"])
    with pytest.raises(EngineError) as info:
        await provider.generate(req("llama3.1:8b"), GeneratedCardBatch, None)
    assert info.value.reason == Reason.INVALID_OUTPUT
