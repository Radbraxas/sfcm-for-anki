# SPDX-License-Identifier: AGPL-3.0-or-later
"""Exported packages import cleanly and update in place on re-import (roadmap B02)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from anki.collection import Collection, ImportAnkiPackageOptions, ImportAnkiPackageRequest

from sfcm_engine.cards import Card
from sfcm_engine.db import Database
from sfcm_engine.deck.fields import to_html
from sfcm_engine.deck.package import clean_deck_name, note_guid, write_package
from sfcm_engine.rpc import Server

from .conftest import Wire


def make_card(card_id: str, **overrides: Any) -> Card:
    base: dict[str, Any] = {
        "id": card_id,
        "note_type": "basic",
        "front": "Which organelle makes most of a cell's **ATP**?",
        "back": "The mitochondrion",
        "text": "",
        "why": "Oxidative phosphorylation happens on its inner membrane.",
        "example": "",
        "mnemonic": "",
        "tags": ["cell-biology"],
        "source": "notes.md",
        "prompt_version": "card_generation@1.0.0",
        "model": "test",
    }
    base.update(overrides)
    return Card(**base)


CARDS = [
    make_card("c1"),
    make_card("c2", note_type="basic_reversed", front="perro", back="dog", why=""),
    make_card(
        "c3",
        note_type="cloze",
        front="",
        back="",
        text="ATP is made in {{c1::mitochondria}} using {{c2::oxygen}}.",
    ),
    make_card("c4", note_type="basic_type_in", front="Spanish for *cat*?", back="gato"),
]


def import_into(col: Collection, package: Path) -> Any:
    request = ImportAnkiPackageRequest(
        package_path=str(package), options=ImportAnkiPackageOptions(with_scheduling=False)
    )
    return col.import_anki_package(request).log


@pytest.mark.parametrize("legacy", [False, True])
def test_package_imports_into_a_fresh_collection(tmp_path: Path, legacy: bool) -> None:
    result = write_package(
        CARDS, tmp_path / "deck.apkg", deck_name="Biology :: Cells", legacy=legacy
    )
    assert (result.notes, result.cards) == (4, 6)  # reversed and 2-deletion cloze add cards
    user = Collection(str(tmp_path / "user.anki2"))
    log = import_into(user, result.path)
    assert len(log.new) == 4
    nids = user.find_notes('"deck:Biology::Cells"')
    assert len(nids) == 4
    note = user.get_note(user.find_notes("perro")[0])
    assert note.guid == note_guid("c2")
    assert "sfcm" in note.tags and "cell-biology" in note.tags
    assert user.models.get(note.mid)["name"] == "SFCM Basic (and reversed card) · Index card"  # type: ignore[index]
    basic = user.get_note(user.find_notes("organelle")[0])
    assert basic["Front"] == "Which organelle makes most of a cell's <b>ATP</b>?"
    user.close()


def test_reimport_updates_fields_and_keeps_review_history(tmp_path: Path) -> None:
    user = Collection(str(tmp_path / "user.anki2"))
    import_into(user, write_package(CARDS, tmp_path / "v1.apkg").path)

    # The user studies the basic card once.
    card = user.get_card(user.find_cards("organelle")[0])
    card.start_timer()
    user.sched.answerCard(card, 3)  # "Good"
    reviews_before = user.db.scalar("SELECT count() FROM revlog")  # type: ignore[union-attr]
    due_before = user.get_card(card.id).due

    time.sleep(1.1)  # Anki compares modification times in whole seconds
    edited = [make_card("c1", back="The **mitochondrion** (plural: mitochondria)"), *CARDS[1:]]
    log = import_into(user, write_package(edited, tmp_path / "v2.apkg").path)

    # Every re-exported note is newer, so Anki reports all four as updated.
    assert (len(log.updated), len(log.new), len(log.conflicting)) == (4, 0, 0)
    assert len(user.find_notes("")) == 4  # no duplicates
    assert "plural" in user.get_note(user.get_card(card.id).nid)["Back"]
    assert user.db.scalar("SELECT count() FROM revlog") == reviews_before  # type: ignore[union-attr]
    assert user.get_card(card.id).due == due_before
    user.close()


def test_field_text_is_escaped() -> None:
    assert to_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert (
        to_html("**bold** and *it* and `a*b*c`")
        == "<b>bold</b> and <i>it</i> and <code>a*b*c</code>"
    )
    assert to_html("line one\nline two") == "line one<br>line two"
    assert to_html(r"{{c1::x < y}} and \(a<b\)") == r"{{c1::x &lt; y}} and \(a&lt;b\)"


def test_deck_names_and_guids() -> None:
    assert clean_deck_name(" Biology ::  :: Cells ") == "Biology::Cells"
    assert clean_deck_name("  ") == "SFCM"
    assert note_guid("c1") == note_guid("c1") != note_guid("c2")
    assert len(note_guid("c1")) == 12


async def test_export_method_validates_path(
    db: Database, server: Server, wire: Wire, tmp_path: Path
) -> None:
    from sfcm_engine.app import App
    from sfcm_engine.llm.registry import ProviderRegistry
    from sfcm_engine.prompts import PromptLibrary

    App(db=db, data_dir=tmp_path, prompts=PromptLibrary(), registry=ProviderRegistry(db)).register(
        server
    )
    cards = [c.model_dump(mode="json", by_alias=True) for c in CARDS]

    def call(params: dict[str, Any], request_id: str) -> None:
        server.handle_line(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": "decks/export", "params": params}
            )
        )

    call({"cards": cards, "outPath": "relative/deck.apkg"}, "bad")
    call({"cards": cards, "outPath": str(tmp_path / "deck.apkg"), "deckName": "Bio"}, "good")
    while len(wire.responses()) < 2:
        await asyncio.sleep(0.05)
    by_id = {r["id"]: r for r in wire.responses()}
    assert by_id["bad"]["error"]["data"]["reason"] == "invalid_export_path"
    assert by_id["good"]["result"] == {"path": str(tmp_path / "deck.apkg"), "notes": 4, "cards": 6}


def test_theme_change_on_reimport_is_a_conflict_not_a_duplicate(tmp_path: Path) -> None:
    """Documents Anki's behavior: restyling imported cards needs a note type change (E07)."""
    user = Collection(str(tmp_path / "user.anki2"))
    import_into(user, write_package(CARDS, tmp_path / "index.apkg", theme="index").path)
    log = import_into(user, write_package(CARDS, tmp_path / "night.apkg", theme="night").path)
    assert (len(log.new), len(log.conflicting)) == (0, 4)
    assert len(user.find_notes("")) == 4
    user.close()
