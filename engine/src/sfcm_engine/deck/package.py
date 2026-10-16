# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write cards to an Anki package (.apkg) (roadmap B02).

Each card's note gets a GUID derived from the card id. When a user imports a newer
export of the same cards, Anki matches notes by GUID and updates their fields in
place, keeping review history, instead of adding duplicates.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from anki.collection import DeckIdLimit, ExportAnkiPackageOptions

from ..cards import Card
from .fields import to_html
from .notetypes import scratch_collection
from .sanitize import sanitize_html

DEFAULT_DECK = "SFCM"
APP_TAG = "sfcm"
_GUID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True)
class ExportResult:
    path: Path
    notes: int
    cards: int


def note_guid(card_id: str) -> str:
    """A 12-character GUID that depends only on the card id."""
    number = int.from_bytes(hashlib.sha256(f"sfcm-note/{card_id}".encode()).digest()[:9], "big")
    chars: list[str] = []
    for _ in range(12):
        number, rem = divmod(number, len(_GUID_ALPHABET))
        chars.append(_GUID_ALPHABET[rem])
    return "".join(chars)


def clean_deck_name(name: str) -> str:
    """Anki deck path with `::` separators and no empty parts."""
    parts = [part.strip() for part in name.split("::")]
    return "::".join(p for p in parts if p) or DEFAULT_DECK


def note_fields(card: Card) -> dict[str, str]:
    fields = {
        "Why": to_html(card.why),
        "Example": to_html(card.example),
        "Mnemonic": to_html(card.mnemonic),
        "Source": to_html(card.source),
    }
    if card.note_type == "cloze":
        fields["Text"] = to_html(card.text)
    else:
        fields["Front"] = to_html(card.front)
        fields["Back"] = to_html(card.back)
    return fields


def write_package(
    cards: Sequence[Card],
    out_path: Path,
    *,
    deck_name: str = DEFAULT_DECK,
    theme: str = "index",
    legacy: bool = False,
) -> ExportResult:
    """Write `cards` into one deck of a new .apkg at `out_path` (overwritten).

    `legacy=True` writes the older package format that Anki versions before 2.1.50
    can read (see docs/anki-compat.md).
    """
    with tempfile.TemporaryDirectory(prefix="sfcm-export-") as tmp:
        col, notetype_ids = scratch_collection(Path(tmp) / "build.anki2", theme)
        try:
            deck_id = col.decks.id(clean_deck_name(deck_name))
            assert deck_id is not None
            card_count = 0
            for card in cards:
                notetype = col.models.get(notetype_ids[card.note_type])
                assert notetype is not None
                note = col.new_note(notetype)
                for name, value in note_fields(card).items():
                    note[name] = sanitize_html(value)
                note.guid = note_guid(card.id)
                note.tags = sorted({*card.tags, APP_TAG})
                col.add_note(note, deck_id)
                card_count += len(note.card_ids())
            col.export_anki_package(
                out_path=str(out_path),
                options=ExportAnkiPackageOptions(
                    with_scheduling=False,
                    with_deck_configs=False,
                    with_media=True,
                    legacy=legacy,
                ),
                limit=DeckIdLimit(deck_id),
            )
        finally:
            col.close()
    return ExportResult(path=out_path, notes=len(cards), cards=card_count)
