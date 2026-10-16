# SPDX-License-Identifier: AGPL-3.0-or-later
"""Live check of every AI provider with a real request (roadmap A09).

    just smoke                      # every provider it can reach
    just smoke anthropic ollama     # only these

Sends the same small generation request (3 cards from a short paragraph) to each
provider, then checks that the reply parses into valid cards. A provider is skipped,
not failed, when its API key is missing or its local server is not running:

    anthropic  ANTHROPIC_API_KEY   ~US$0.02 per run with claude-opus-5-5
    openai     OPENAI_API_KEY      ~US$0.01 per run
    ollama     server on http://localhost:11434 with the model pulled (free)
    lmstudio   server on http://localhost:1234 with a model loaded (free)

Model overrides: SFCM_SMOKE_<PROVIDER>_MODEL, e.g. SFCM_SMOKE_OLLAMA_MODEL=qwen3:8b.
Exit code is 1 if any provider that was tried failed.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import urllib.request
from typing import get_args

from sfcm_engine.db import Database
from sfcm_engine.errors import EngineError
from sfcm_engine.generation import generate_cards
from sfcm_engine.llm.registry import DEFAULTS, ProviderRegistry
from sfcm_engine.prompts import PromptLibrary
from sfcm_engine.protocol import CardsGenerateParams, ProviderId
from sfcm_engine.secrets import EnvKeySource

SOURCE = (
    "Mitochondria produce most of a cell's ATP through oxidative phosphorylation on the "
    "inner mitochondrial membrane. They carry their own circular DNA, inherited from the "
    "mother, which supports the theory that they descend from engulfed bacteria."
)


def server_up(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/models", timeout=2):  # noqa: S310
            return True
    except OSError:
        return False


async def check(provider_id: ProviderId, registry: ProviderRegistry) -> str:
    provider = registry.build(provider_id)
    key = await EnvKeySource().get(provider_id) if provider.needs_api_key else None
    if provider.needs_api_key and not key:
        return f"SKIP  {provider_id:<9} no {provider_id.upper()}_API_KEY in the environment"
    if provider.location == "local" and not server_up(str(provider.base_url)):
        return f"SKIP  {provider_id:<9} no server at {provider.base_url}"
    model = os.environ.get(f"SFCM_SMOKE_{provider_id.upper()}_MODEL") or registry.model_for(
        provider_id
    )
    started = time.monotonic()
    try:
        outcome = await generate_cards(
            CardsGenerateParams(source=SOURCE, source_label="smoke test", count=3),
            provider=provider,
            model=model,
            api_key=key,
            prompts=PromptLibrary(),
        )
    except EngineError as exc:
        return f"FAIL  {provider_id:<9} {model}: {exc.reason}: {exc.message}"
    seconds = time.monotonic() - started
    if not outcome.cards:
        return (
            f"FAIL  {provider_id:<9} {outcome.model}: 0 valid cards ({outcome.rejected} rejected)"
        )
    cost = "n/a" if outcome.usage.cost_usd is None else f"${outcome.usage.cost_usd:.4f}"
    first = outcome.cards[0]
    sample = first.text if first.note_type == "cloze" else f"{first.front} -> {first.back}"
    return (
        f"PASS  {provider_id:<9} {outcome.model}: {len(outcome.cards)} cards, "
        f"{outcome.rejected} rejected, {seconds:.1f}s, cost {cost}\n"
        f"      e.g. [{first.note_type}] {sample[:110]}"
    )


async def main_async(wanted: list[str]) -> int:
    all_ids: tuple[ProviderId, ...] = get_args(ProviderId)
    unknown = [w for w in wanted if w not in all_ids]
    if unknown:
        print(f"unknown provider(s): {', '.join(unknown)}; choose from {', '.join(all_ids)}")
        return 2
    db = Database(":memory:")
    db.migrate()
    registry = ProviderRegistry(db)
    failed = False
    selected: list[ProviderId] = [p for p in all_ids if not wanted or str(p) in wanted]
    for pid in selected:
        print(f"...   {pid:<9} {DEFAULTS[pid]['name']}", flush=True)
        line = await check(pid, registry)
        failed |= line.startswith("FAIL")
        print(line, flush=True)
    return 1 if failed else 0


def main() -> int:
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
