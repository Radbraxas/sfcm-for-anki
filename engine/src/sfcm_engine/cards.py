# SPDX-License-Identifier: AGPL-3.0-or-later
"""The one card format shared by all three features (roadmap A10).

`GeneratedCard` is what a model is asked to produce; its JSON Schema is sent as the
structured-output format, so every field is required (empty string when unused).
`Card` adds what the engine stamps on afterwards.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# Image Occlusion is created by hand in the UI (roadmap C07), never by a model.
NoteType = Literal[
    "basic",
    "basic_reversed",
    "basic_optional_reversed",
    "basic_type_in",
    "cloze",
]

GENERATABLE_NOTE_TYPES: tuple[NoteType, ...] = (
    "basic",
    "basic_reversed",
    "basic_optional_reversed",
    "basic_type_in",
    "cloze",
)


class CamelModel(BaseModel):
    """camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        # Output schemas list defaulted fields as required: they are always sent.
        json_schema_serialization_defaults_required=True,
    )


class GeneratedCard(CamelModel):
    note_type: NoteType = Field(description="Anki note type that fits this fact best.")
    front: str = Field(description="Question side. Empty for cloze cards.")
    back: str = Field(description="Short answer, ideally under 15 words. Empty for cloze.")
    text: str = Field(description="Cloze sentence with {{c1::...}} deletions. Empty otherwise.")
    why: str = Field(description="1-2 sentences on why the answer is true. May be empty.")
    example: str = Field(description="A concrete example. May be empty.")
    mnemonic: str = Field(description="A memory hook, only if genuinely useful. May be empty.")
    tags: list[str] = Field(description="1-3 lowercase-hyphenated topic tags.")


class GeneratedCardBatch(CamelModel):
    cards: list[GeneratedCard]


class Card(GeneratedCard):
    id: str
    source: str = Field(description="Where the card came from, e.g. a file and heading.")
    prompt_version: str
    model: str
