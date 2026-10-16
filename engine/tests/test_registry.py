# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import pytest

from sfcm_engine.db import Database
from sfcm_engine.errors import EngineError, Reason
from sfcm_engine.llm.registry import ProviderRegistry


def test_defaults(db: Database) -> None:
    registry = ProviderRegistry(db)
    assert registry.active_id() == "anthropic"
    assert registry.model_for("anthropic") == "claude-opus-5-5"
    assert {p.id: p.location for p in registry.describe()} == {
        "anthropic": "cloud",
        "openai": "cloud",
        "ollama": "local",
        "lmstudio": "local",
        "custom": "cloud",
    }


def test_custom_needs_base_url_and_model(db: Database) -> None:
    with pytest.raises(EngineError) as info:
        ProviderRegistry(db).resolve("custom")
    assert info.value.reason == Reason.PROVIDER_NOT_CONFIGURED
    assert info.value.details["missing"] == ["llm.custom.baseUrl", "llm.custom.model"]

    db.set_setting("llm.custom.baseUrl", "https://api.groq.com/openai/v1")
    with pytest.raises(EngineError) as info:
        ProviderRegistry(db).resolve("custom")
    assert info.value.details["missing"] == ["llm.custom.model"]


def test_custom_cloud_endpoint(db: Database) -> None:
    db.set_setting("llm.custom.baseUrl", "https://api.groq.com/openai/v1")
    db.set_setting("llm.custom.model", "llama-3.3-70b-versatile")
    provider = ProviderRegistry(db).resolve("custom")
    assert provider.location == "cloud"
    assert provider.needs_api_key
    info = next(p for p in ProviderRegistry(db).describe() if p.id == "custom")
    assert info.needs_api_key
    assert info.default_model == "llama-3.3-70b-versatile"


def test_local_only_blocks_remote_custom_endpoint(db: Database) -> None:
    db.set_setting("llm.localOnly", True)
    db.set_setting("llm.custom.baseUrl", "https://openrouter.ai/api/v1")
    db.set_setting("llm.custom.model", "some/model:free")
    with pytest.raises(EngineError) as info:
        ProviderRegistry(db).resolve("custom")
    assert info.value.reason == Reason.LOCAL_ONLY_BLOCKED


def test_local_only_allows_localhost_custom_endpoint(db: Database) -> None:
    db.set_setting("llm.localOnly", True)
    db.set_setting("llm.custom.baseUrl", "http://localhost:8080/v1")
    db.set_setting("llm.custom.model", "qwen3")
    provider = ProviderRegistry(db).resolve("custom")
    assert provider.location == "local"
    assert not provider.needs_api_key


@pytest.mark.parametrize("provider_id", ["anthropic", "openai"])
def test_local_only_blocks_cloud_providers(db: Database, provider_id: str) -> None:
    db.set_setting("llm.localOnly", True)
    with pytest.raises(EngineError) as info:
        ProviderRegistry(db).resolve(provider_id)  # type: ignore[arg-type]
    assert info.value.reason == Reason.LOCAL_ONLY_BLOCKED


def test_local_only_allows_localhost(db: Database) -> None:
    db.set_setting("llm.localOnly", True)
    assert ProviderRegistry(db).resolve("ollama").location == "local"


def test_local_only_blocks_remote_ollama_endpoint(db: Database) -> None:
    """A 'local' provider pointed at another machine is not local any more."""
    db.set_setting("llm.localOnly", True)
    db.set_setting("llm.ollama.baseUrl", "http://gpu-box.example.com:11434/v1")
    with pytest.raises(EngineError):
        ProviderRegistry(db).resolve("ollama")
    assert next(
        p for p in ProviderRegistry(db).describe() if p.id == "ollama"
    ).blocked_by_local_only


def test_model_override(db: Database) -> None:
    db.set_setting("llm.anthropic.model", "claude-sonnet-5-5")
    assert ProviderRegistry(db).model_for("anthropic") == "claude-sonnet-5-5"


def test_listing_providers_does_not_import_sdks(db: Database) -> None:
    """Startup speed: SDKs load only when a provider is actually built."""
    import subprocess
    import sys

    code = (
        "import sys; from sfcm_engine.app import App; "
        "from sfcm_engine.db import Database; "
        "from sfcm_engine.llm.registry import ProviderRegistry; "
        "db = Database(':memory:'); db.migrate(); ProviderRegistry(db).describe(); "
        "print('anthropic' in sys.modules, 'openai' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False False"
