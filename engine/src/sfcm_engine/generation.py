# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn source text into validated cards. Shared by the app, the CLI and the evals."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from .cards import Card, GeneratedCardBatch
from .llm.base import Provider, StructuredRequest
from .prompts import PromptLibrary
from .protocol import CardsGenerateParams, Usage
from .quality.lint import has_errors, lint_card, normalize_tags

PROMPT_NAME = "card_generation"

AUDIENCES = {
    "intro": "a learner meeting this topic for the first time",
    "university": "a university student preparing for an exam",
    "expert": "an expert who wants precise, nuanced, non-obvious details",
}
MIX = {
    "auto": "choose the best note type for each fact",
    "basic": "use only basic, basic_reversed, basic_optional_reversed or basic_type_in",
    "cloze": "use only cloze",
}
EXTRAS = {
    "all": "fill why and example where useful, and mnemonic only when it is genuinely memorable",
    "why": "fill why and example where useful; leave mnemonic empty",
    "none": "leave why, example and mnemonic empty",
}

Progress = Callable[[str, float | None], None]


@dataclass
class GenerationOutcome:
    cards: list[Card]
    rejected: int
    prompt_version: str
    model: str
    usage: Usage


async def generate_cards(
    params: CardsGenerateParams,
    *,
    provider: Provider,
    model: str,
    api_key: str | None,
    prompts: PromptLibrary,
    progress: Progress = lambda _m, _f: None,
) -> GenerationOutcome:
    progress("preparing_prompt", 0.05)
    prompt = prompts.render(
        PROMPT_NAME,
        count=params.count,
        language=params.language,
        audience=AUDIENCES[params.depth],
        mix_instruction=MIX[params.mix],
        extras_instruction=EXTRAS[params.extras],
        source_label=params.source_label,
        source=params.source,
    )
    progress("calling_provider", 0.1)
    result = await provider.generate(
        StructuredRequest(system=prompt.system, user=prompt.user, model=model),
        GeneratedCardBatch,
        api_key,
    )
    progress("validating", 0.9)

    cards: list[Card] = []
    rejected = 0
    for generated in result.value.cards:
        if has_errors(lint_card(generated)):
            rejected += 1
            continue
        is_cloze = generated.note_type == "cloze"
        if (params.mix == "cloze" and not is_cloze) or (params.mix == "basic" and is_cloze):
            rejected += 1
            continue
        cards.append(
            Card(
                **generated.model_dump(exclude={"tags"}),
                tags=normalize_tags(generated.tags),
                id=str(uuid.uuid4()),
                source=params.source_label,
                prompt_version=prompt.version,
                model=result.model,
            )
        )
    progress("done", 1.0)
    return GenerationOutcome(
        cards=cards,
        rejected=rejected,
        prompt_version=prompt.version,
        model=result.model,
        usage=result.usage,
    )
