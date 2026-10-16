# SPDX-License-Identifier: AGPL-3.0-or-later
"""The UI <-> engine protocol (roadmap A07).

Every method, its params and its result are declared here once. `export_schema.py`
turns this module into engine/schema/protocol.schema.json, and the UI generates its
TypeScript types from that file. Change this module, then run `just gen`.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, JsonValue

from .cards import CamelModel, Card

ProviderId = Literal["anthropic", "openai", "ollama", "lmstudio", "custom"]
Effort = Literal["low", "medium", "high"]


class Empty(CamelModel):
    pass


# --- engine/* ---------------------------------------------------------------


class EngineInfo(CamelModel):
    engine_version: str
    protocol_version: int
    python_version: str
    anki_version: str | None = Field(description="Version of the anki package, if bundled.")
    data_dir: str


# --- settings/* -------------------------------------------------------------


class SettingsGetParams(CamelModel):
    key: str


class SettingsSetParams(CamelModel):
    key: str
    value: JsonValue


class SettingValue(CamelModel):
    key: str
    value: JsonValue


# --- providers/* ------------------------------------------------------------


class ProviderInfo(CamelModel):
    id: ProviderId
    name: str
    location: Literal["cloud", "local"]
    needs_api_key: bool
    default_model: str
    base_url: str | None
    blocked_by_local_only: bool


class ProviderList(CamelModel):
    providers: list[ProviderInfo]
    local_only: bool
    active_provider: ProviderId


class ProviderTestParams(CamelModel):
    provider_id: ProviderId
    model: str | None = None


class ProviderTestResult(CamelModel):
    ok: bool
    model: str
    latency_ms: int


# --- cards/* ----------------------------------------------------------------


class CardsGenerateParams(CamelModel):
    source: str = Field(min_length=1, max_length=400_000)
    source_label: str = "pasted text"
    count: int = Field(default=12, ge=1, le=60)
    mix: Literal["auto", "basic", "cloze"] = "auto"
    depth: Literal["intro", "university", "expert"] = "university"
    language: str = "English"
    extras: Literal["all", "why", "none"] = "all"
    provider_id: ProviderId | None = None
    model: str | None = None


class Usage(CamelModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None


class CardsGenerateResult(CamelModel):
    cards: list[Card]
    rejected: int = Field(description="Cards dropped by validation.")
    prompt_version: str
    model: str
    usage: Usage


# --- decks/* ----------------------------------------------------------------

ThemeKey = Literal["index"]


class DecksExportParams(CamelModel):
    cards: list[Card] = Field(min_length=1)
    out_path: str = Field(description="Absolute path of the .apkg to write; overwritten.")
    deck_name: str = Field(default="SFCM", description="Anki deck path, `::` for subdecks.")
    theme: ThemeKey = "index"
    legacy: bool = Field(default=False, description="Older package format for Anki < 2.1.50.")


class DecksExportResult(CamelModel):
    path: str
    notes: int
    cards: int = Field(description="Review cards created (reversed and cloze notes make more).")


# --- Notifications (engine -> UI) --------------------------------------------


class ReadyParams(CamelModel):
    engine_version: str
    protocol_version: int


class ProgressParams(CamelModel):
    request_id: str | int
    message: str = Field(description="Stable progress key, e.g. 'calling_provider'.")
    fraction: float | None = None


# --- Requests the engine makes to the Rust shell ------------------------------


class SecretsGetParams(CamelModel):
    service: ProviderId


class SecretsGetResult(CamelModel):
    value: str | None


# --- Registry -----------------------------------------------------------------

# method -> (params model, result model)
METHODS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "engine/info": (Empty, EngineInfo),
    "settings/get": (SettingsGetParams, SettingValue),
    "settings/set": (SettingsSetParams, SettingValue),
    "providers/list": (Empty, ProviderList),
    "providers/test": (ProviderTestParams, ProviderTestResult),
    "cards/generate": (CardsGenerateParams, CardsGenerateResult),
    "decks/export": (DecksExportParams, DecksExportResult),
}

SHELL_METHODS: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "secrets/get": (SecretsGetParams, SecretsGetResult),
}

NOTIFICATIONS: dict[str, type[BaseModel]] = {
    "$/ready": ReadyParams,
    "$/progress": ProgressParams,
}


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)
