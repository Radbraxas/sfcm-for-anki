# SPDX-License-Identifier: AGPL-3.0-or-later
"""The SFCM note types and how to install them into a collection (roadmap B01).

Anki matches note types between a package and a collection by id, and checks that
their fields and templates have the same ids. Anki assigns random ids when a note
type is added, so every export would look like a new note type and re-imports would
create copies ("SFCM Basic+") instead of updating cards. We therefore give each note
type, field and template a fixed id derived from its name. Anki has no API to choose
a note type id, so `scratch_collection` rewrites it in a throwaway collection that is
only used for building packages.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anki.collection import Collection
from anki.consts import MODEL_CLOZE
from anki.models import NotetypeId
from anki.stdmodels import StockNotetypeKind
from anki.utils import from_json_bytes

from ..cards import NoteType
from . import templates as t
from .themes import THEMES, Theme

# Note type ids look like Anki's own (millisecond timestamps), in a range of our own:
# BASE + theme slot * 100 + note type slot.
BASE_ID = 1_731_000_000_000
EXTRA_FIELDS = ("Why", "Example", "Mnemonic", "Source")


@dataclass(frozen=True)
class TemplateSpec:
    name: str
    qfmt: str
    afmt: str


@dataclass(frozen=True)
class NoteTypeSpec:
    key: NoteType
    slot: int  # never reuse or renumber: it is part of the stable id
    label: str
    fields: tuple[str, ...]
    templates: tuple[TemplateSpec, ...]
    cloze: bool = False


BASIC_FIELDS = ("Front", "Back", *EXTRA_FIELDS)

SPECS: dict[NoteType, NoteTypeSpec] = {
    "basic": NoteTypeSpec(
        "basic",
        1,
        "Basic",
        BASIC_FIELDS,
        (TemplateSpec("Card 1", t.front("Front", "Question"), t.back("Back")),),
    ),
    "basic_reversed": NoteTypeSpec(
        "basic_reversed",
        2,
        "Basic (and reversed card)",
        BASIC_FIELDS,
        (
            TemplateSpec("Card 1", t.front("Front", "Question"), t.back("Back")),
            TemplateSpec("Card 2", t.front("Back", "Reverse"), t.back("Front")),
        ),
    ),
    "basic_optional_reversed": NoteTypeSpec(
        "basic_optional_reversed",
        3,
        "Basic (optional reversed card)",
        ("Front", "Back", "Add Reverse", *EXTRA_FIELDS),
        (
            TemplateSpec("Card 1", t.front("Front", "Question"), t.back("Back")),
            TemplateSpec(
                "Card 2",
                "{{#Add Reverse}}" + t.front("Back", "Reverse") + "{{/Add Reverse}}",
                t.back("Front"),
            ),
        ),
    ),
    "basic_type_in": NoteTypeSpec(
        "basic_type_in",
        4,
        "Basic (type in the answer)",
        BASIC_FIELDS,
        (TemplateSpec("Card 1", t.TYPE_IN_FRONT, t.TYPE_IN_BACK),),
    ),
    "cloze": NoteTypeSpec(
        "cloze",
        5,
        "Cloze",
        ("Text", *EXTRA_FIELDS),
        (TemplateSpec("Cloze", t.CLOZE_FRONT, t.CLOZE_BACK),),
        cloze=True,
    ),
}


def stable_id(*parts: str) -> int:
    """A signed 64-bit id that depends only on `parts` (Anki stores ids as i64)."""
    digest = hashlib.sha256("/".join(("sfcm", *parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def notetype_id(spec: NoteTypeSpec, theme: Theme) -> NotetypeId:
    return NotetypeId(BASE_ID + theme.slot * 100 + spec.slot)


def notetype_name(spec: NoteTypeSpec, theme: Theme) -> str:
    return f"SFCM {spec.label} · {theme.name}"


def build_notetype(col: Collection, spec: NoteTypeSpec, theme: Theme) -> dict[str, Any]:
    mm = col.models
    kind = StockNotetypeKind.KIND_CLOZE if spec.cloze else StockNotetypeKind.KIND_BASIC
    nt: dict[str, Any] = from_json_bytes(col._backend.get_stock_notetype_legacy(kind))  # pyright: ignore[reportPrivateUsage]
    nt["name"] = notetype_name(spec, theme)
    nt["flds"] = []
    nt["tmpls"] = []
    if spec.cloze:
        nt["type"] = MODEL_CLOZE
    for field_name in spec.fields:
        field = mm.new_field(field_name)
        field["id"] = stable_id(theme.key, spec.key, "field", field_name)
        mm.add_field(nt, field)
    for tmpl in spec.templates:
        template = mm.new_template(tmpl.name)
        template["qfmt"] = tmpl.qfmt
        template["afmt"] = tmpl.afmt
        template["id"] = stable_id(theme.key, spec.key, "template", tmpl.name)
        mm.add_template(nt, template)
    nt["css"] = theme.css
    nt["sortf"] = 0
    return nt


def scratch_collection(path: Path, theme_key: str) -> tuple[Collection, dict[NoteType, NotetypeId]]:
    """Open a new, empty collection at `path` holding the SFCM note types for a theme.

    Only for building packages: note type ids are rewritten directly in the database.
    """
    theme = THEMES[theme_key]
    col = Collection(str(path))
    db = col.db
    assert db is not None
    ids: dict[NoteType, NotetypeId] = {}
    for spec in SPECS.values():
        assigned = col.models.add_dict(build_notetype(col, spec, theme)).id  # pyright: ignore[reportArgumentType]
        wanted = notetype_id(spec, theme)
        for table, column in (("notetypes", "id"), ("fields", "ntid"), ("templates", "ntid")):
            db.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", wanted, assigned)  # noqa: S608 - fixed names
        ids[spec.key] = wanted
    col.close()
    # Reopen so Anki's caches see the rewritten ids.
    return Collection(str(path)), ids
