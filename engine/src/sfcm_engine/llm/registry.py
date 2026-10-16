# SPDX-License-Identifier: AGPL-3.0-or-later
"""Builds providers from settings and enforces the "local only" switch (A09, A13).

Settings keys (all optional):
  llm.provider                 active provider id (default "anthropic")
  llm.localOnly                true blocks every provider whose endpoint is not localhost
  llm.<provider>.model         model override
  llm.<provider>.baseUrl       endpoint override (OpenAI-compatible providers only)

The "custom" provider is any OpenAI-compatible endpoint (Gemini, Groq, OpenRouter, a
self-hosted server). It has no defaults: llm.custom.baseUrl and llm.custom.model must
both be set before it can be used.
"""

from __future__ import annotations

from typing import Any, get_args

from ..db import Database
from ..errors import EngineError, Reason
from ..protocol import ProviderId, ProviderInfo
from .base import Location, Provider, is_local_url

# Provider modules import their SDKs, which take seconds to load. They are imported
# on first use so the engine reports ready quickly (roadmap A06: start in under 2 s).

PROVIDER_IDS: tuple[ProviderId, ...] = get_args(ProviderId)

DEFAULTS: dict[ProviderId, dict[str, Any]] = {
    "anthropic": {"name": "Anthropic Claude", "model": "claude-opus-5-5", "baseUrl": None},
    "openai": {"name": "OpenAI", "model": "gpt-5-mini", "baseUrl": "https://api.openai.com/v1"},
    "ollama": {
        "name": "Ollama (local)",
        "model": "llama3.1:8b",
        "baseUrl": "http://localhost:11434/v1",
    },
    "lmstudio": {
        "name": "LM Studio (local)",
        "model": "local-model",
        "baseUrl": "http://localhost:1234/v1",
    },
    "custom": {"name": "Custom (OpenAI-compatible)", "model": None, "baseUrl": None},
}

# The model the eval harness and quality checks use as a judge.
JUDGE_MODEL = "claude-haiku-5-5"


class ProviderRegistry:
    def __init__(self, db: Database, overrides: dict[ProviderId, Provider] | None = None) -> None:
        self._db = db
        self._overrides = overrides or {}

    def local_only(self) -> bool:
        return bool(self._db.get_setting("llm.localOnly", False))

    def active_id(self) -> ProviderId:
        value = self._db.get_setting("llm.provider", "anthropic")
        return value if value in PROVIDER_IDS else "anthropic"

    def model_for(self, provider_id: ProviderId) -> str:
        value = self._db.get_setting(f"llm.{provider_id}.model", DEFAULTS[provider_id]["model"])
        return str(value or "").strip()

    def base_url(self, provider_id: ProviderId) -> str | None:
        if provider_id == "anthropic":
            return None
        value = self._db.get_setting(f"llm.{provider_id}.baseUrl", DEFAULTS[provider_id]["baseUrl"])
        return str(value or "").strip() or None

    def needs_api_key(self, provider_id: ProviderId) -> bool:
        if provider_id == "custom":
            # A custom endpoint on this computer (e.g. llama.cpp) usually has no key.
            return not is_local_url(self.base_url(provider_id))
        return provider_id in ("anthropic", "openai")

    def missing_settings(self, provider_id: ProviderId) -> list[str]:
        """Settings that must be filled in before this provider can be called."""
        if provider_id != "custom":
            return []
        missing: list[str] = []
        if not self.base_url(provider_id):
            missing.append(f"llm.{provider_id}.baseUrl")
        if not self.model_for(provider_id):
            missing.append(f"llm.{provider_id}.model")
        return missing

    def location(self, provider_id: ProviderId) -> Location:
        if provider_id in self._overrides:
            return self._overrides[provider_id].location
        return "local" if is_local_url(self.base_url(provider_id)) else "cloud"

    def build(self, provider_id: ProviderId) -> Provider:
        if provider_id in self._overrides:
            return self._overrides[provider_id]
        if provider_id == "anthropic":
            from .anthropic_provider import AnthropicProvider

            return AnthropicProvider()
        from .openai_compat import OpenAICompatibleProvider

        defaults = DEFAULTS[provider_id]
        base_url = self.base_url(provider_id)
        return OpenAICompatibleProvider(
            id=provider_id,
            name=defaults["name"],
            default_model=self.model_for(provider_id),
            base_url=base_url,
            needs_api_key=self.needs_api_key(provider_id),
        )

    def resolve(self, provider_id: ProviderId | None = None) -> Provider:
        """The provider to call, after the local-only check."""
        pid = provider_id or self.active_id()
        if pid not in PROVIDER_IDS:
            raise EngineError(Reason.UNKNOWN_PROVIDER, f"unknown provider {pid}")
        missing = self.missing_settings(pid)
        if missing:
            raise EngineError(
                Reason.PROVIDER_NOT_CONFIGURED,
                f"{DEFAULTS[pid]['name']} needs {' and '.join(missing)} set first",
                provider=pid,
                missing=missing,
            )
        if self.local_only() and self.location(pid) != "local":
            raise EngineError(
                Reason.LOCAL_ONLY_BLOCKED,
                f"{DEFAULTS[pid]['name']} sends data off this computer and local-only mode is on",
                provider=pid,
            )
        return self.build(pid)

    def describe(self) -> list[ProviderInfo]:
        local_only = self.local_only()
        infos: list[ProviderInfo] = []
        for pid in PROVIDER_IDS:
            location = self.location(pid)
            infos.append(
                ProviderInfo(
                    id=pid,
                    name=DEFAULTS[pid]["name"],
                    location=location,
                    needs_api_key=self.needs_api_key(pid),
                    default_model=self.model_for(pid),
                    base_url=self.base_url(pid),
                    blocked_by_local_only=local_only and location != "local",
                )
            )
        return infos
