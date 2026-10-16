# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from sfcm_engine.cards import GeneratedCard, GeneratedCardBatch
from sfcm_engine.db import Database
from sfcm_engine.llm.base import Location, StructuredRequest, StructuredResult
from sfcm_engine.protocol import ProviderId, Usage
from sfcm_engine.rpc import Server


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    database.migrate()
    return database


@dataclass
class Wire:
    """Collects what the server sends, decoded."""

    messages: list[dict[str, Any]] = field(default_factory=lambda: [])

    def send(self, msg: dict[str, Any]) -> None:
        # Round-trip through JSON so tests see exactly what goes on the wire.
        self.messages.append(json.loads(json.dumps(msg)))

    def responses(self) -> list[dict[str, Any]]:
        return [m for m in self.messages if "id" in m and "method" not in m]

    def notifications(self, method: str) -> list[dict[str, Any]]:
        return [m for m in self.messages if m.get("method") == method and "id" not in m]


@pytest.fixture
def wire() -> Wire:
    return Wire()


@pytest.fixture
def server(wire: Wire) -> Server:
    return Server(send=wire.send, shell_timeout=1.0)


def card(**overrides: Any) -> GeneratedCard:
    base: dict[str, Any] = {
        "note_type": "basic",
        "front": "Which organelle produces most of a cell's ATP?",
        "back": "The **mitochondrion**",
        "text": "",
        "why": "Oxidative phosphorylation happens on its inner membrane.",
        "example": "",
        "mnemonic": "",
        "tags": ["cell-biology"],
    }
    base.update(overrides)
    return GeneratedCard(**base)


@dataclass
class FakeProvider:
    """A provider that returns canned cards and records what it was asked."""

    cards: list[GeneratedCard]
    id: ProviderId = "anthropic"
    name: str = "Fake"
    location: Location = "cloud"
    needs_api_key: bool = True
    default_model: str = "fake-model"
    base_url: str | None = None
    requests: list[StructuredRequest] = field(default_factory=lambda: [])

    async def generate(self, request: StructuredRequest, output: Any, api_key: str | None) -> Any:
        self.requests.append(request)
        value = output.model_validate(GeneratedCardBatch(cards=self.cards).model_dump())
        return StructuredResult(
            value=value, usage=Usage(input_tokens=100, output_tokens=50), model=request.model
        )
