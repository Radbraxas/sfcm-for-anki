# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wires protocol methods to their implementations."""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from . import PROTOCOL_VERSION, __version__
from .db import Database
from .generation import generate_cards
from .llm.base import StructuredRequest
from .llm.registry import ProviderRegistry
from .prompts import PromptLibrary
from .protocol import (
    CardsGenerateParams,
    CardsGenerateResult,
    Empty,
    EngineInfo,
    ProviderList,
    ProviderTestParams,
    ProviderTestResult,
    SettingsGetParams,
    SettingsSetParams,
    SettingValue,
)
from .rpc import Context, Server
from .secrets import KeySource, ShellKeySource


def anki_version() -> str | None:
    try:
        return metadata.version("anki")
    except metadata.PackageNotFoundError:
        return None


class _Ping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


@dataclass
class App:
    db: Database
    data_dir: Path
    prompts: PromptLibrary
    registry: ProviderRegistry
    keys: KeySource | None = None  # None: ask the shell (the normal case)

    def key_source(self, ctx: Context) -> KeySource:
        return self.keys or ShellKeySource(ctx.call_shell)

    def register(self, server: Server) -> None:
        server.method("engine/info")(self.engine_info)
        server.method("settings/get")(self.settings_get)
        server.method("settings/set")(self.settings_set)
        server.method("providers/list")(self.providers_list)
        server.method("providers/test")(self.providers_test)
        server.method("cards/generate")(self.cards_generate)

    async def engine_info(self, _params: Empty, _ctx: Context) -> EngineInfo:
        return EngineInfo(
            engine_version=__version__,
            protocol_version=PROTOCOL_VERSION,
            python_version=platform.python_version(),
            anki_version=anki_version(),
            data_dir=str(self.data_dir),
        )

    async def settings_get(self, params: SettingsGetParams, _ctx: Context) -> SettingValue:
        return SettingValue(key=params.key, value=self.db.get_setting(params.key))

    async def settings_set(self, params: SettingsSetParams, _ctx: Context) -> SettingValue:
        self.db.set_setting(params.key, params.value)
        return SettingValue(key=params.key, value=params.value)

    async def providers_list(self, _params: Empty, _ctx: Context) -> ProviderList:
        return ProviderList(
            providers=self.registry.describe(),
            local_only=self.registry.local_only(),
            active_provider=self.registry.active_id(),
        )

    async def providers_test(self, params: ProviderTestParams, ctx: Context) -> ProviderTestResult:
        provider = self.registry.resolve(params.provider_id)
        model = params.model or self.registry.model_for(provider.id)
        api_key = await self.key_source(ctx).get(provider.id) if provider.needs_api_key else None
        started = time.monotonic()
        result = await provider.generate(
            StructuredRequest(
                system="You are a connectivity check.",
                user='Reply with {"ok": true}.',
                model=model,
                effort="low",
                max_tokens=2_000,
            ),
            _Ping,
            api_key,
        )
        return ProviderTestResult(
            ok=result.value.ok,
            model=result.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def cards_generate(
        self, params: CardsGenerateParams, ctx: Context
    ) -> CardsGenerateResult:
        provider = self.registry.resolve(params.provider_id)
        model = params.model or self.registry.model_for(provider.id)
        api_key = await self.key_source(ctx).get(provider.id) if provider.needs_api_key else None
        outcome = await generate_cards(
            params,
            provider=provider,
            model=model,
            api_key=api_key,
            prompts=self.prompts,
            progress=ctx.progress,
        )
        self.db.conn.execute(
            "INSERT INTO generation_log (provider, model, prompt_name, prompt_version,"
            " input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd,"
            " cards_accepted, cards_rejected) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                provider.id,
                outcome.model,
                "card_generation",
                outcome.prompt_version,
                outcome.usage.input_tokens,
                outcome.usage.output_tokens,
                outcome.usage.cache_read_tokens,
                outcome.usage.cache_write_tokens,
                outcome.usage.cost_usd,
                len(outcome.cards),
                outcome.rejected,
            ),
        )
        return CardsGenerateResult(
            cards=outcome.cards,
            rejected=outcome.rejected,
            prompt_version=outcome.prompt_version,
            model=outcome.model,
            usage=outcome.usage,
        )
