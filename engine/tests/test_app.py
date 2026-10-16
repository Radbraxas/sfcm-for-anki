# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from sfcm_engine.app import App
from sfcm_engine.db import Database
from sfcm_engine.llm.registry import ProviderRegistry
from sfcm_engine.prompts import PromptLibrary
from sfcm_engine.rpc import Server

from .conftest import FakeProvider, Wire, card


class StaticKeys:
    async def get(self, service: str) -> str | None:
        return "sk-ant-test-key-000000"


def make_app(db: Database, provider: FakeProvider) -> App:
    return App(
        db=db,
        data_dir=Path("/tmp"),
        prompts=PromptLibrary(),
        registry=ProviderRegistry(db, overrides={"anthropic": provider}),
        keys=StaticKeys(),
    )


async def call(server: Server, wire: Wire, method: str, params: object) -> dict[str, Any]:
    server.handle_line(
        json.dumps({"jsonrpc": "2.0", "id": "r1", "method": method, "params": params})
    )
    while not wire.responses():
        await asyncio.sleep(0.01)
    return wire.responses()[-1]


async def test_generate_filters_and_stamps_cards(db: Database, server: Server, wire: Wire) -> None:
    provider = FakeProvider(
        cards=[
            card(),
            card(note_type="cloze", front="", back="", text="ATP comes from {{c1::mitochondria}}."),
            card(note_type="cloze", front="", back="", text="Broken cloze with no deletion"),
            card(tags=["Cell Biology", "ATP"]),
        ]
    )
    make_app(db, provider).register(server)
    response = await call(
        server, wire, "cards/generate", {"source": "Mitochondria make ATP.", "count": 4}
    )
    result: dict[str, Any] = response["result"]
    cards: list[dict[str, Any]] = result["cards"]
    assert result["rejected"] == 1
    assert [c["noteType"] for c in cards] == ["basic", "cloze", "basic"]
    assert cards[2]["tags"] == ["cell-biology", "atp"]
    assert result["promptVersion"] == "card_generation@1.0.0"
    assert all(c["source"] == "pasted text" for c in cards)
    assert provider.requests[0].model == "claude-opus-5-5"
    assert "Mitochondria make ATP." in provider.requests[0].user
    messages = [n["params"]["message"] for n in wire.notifications("$/progress")]
    assert messages == ["preparing_prompt", "calling_provider", "validating", "done"]
    logged = db.conn.execute("SELECT cards_accepted, cards_rejected FROM generation_log").fetchall()
    assert logged == [(3, 1)]


async def test_cloze_only_mix_drops_basic_cards(db: Database, server: Server, wire: Wire) -> None:
    provider = FakeProvider(
        cards=[card(), card(note_type="cloze", front="", back="", text="{{c1::A}} b.")]
    )
    make_app(db, provider).register(server)
    response = await call(server, wire, "cards/generate", {"source": "x", "mix": "cloze"})
    result: dict[str, Any] = response["result"]
    cards: list[dict[str, Any]] = result["cards"]
    assert [c["noteType"] for c in cards] == ["cloze"]


async def test_local_only_error_reaches_client(db: Database, server: Server, wire: Wire) -> None:
    db.set_setting("llm.localOnly", True)
    App(
        db=db, data_dir=Path("/tmp"), prompts=PromptLibrary(), registry=ProviderRegistry(db)
    ).register(server)
    response = await call(server, wire, "cards/generate", {"source": "x"})
    assert response["error"]["data"]["reason"] == "local_only_blocked"


async def test_engine_info(db: Database, server: Server, wire: Wire) -> None:
    make_app(db, FakeProvider(cards=[])).register(server)
    response = await call(server, wire, "engine/info", {})
    assert response["result"]["protocolVersion"] == 1
