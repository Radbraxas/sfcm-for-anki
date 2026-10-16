# SPDX-License-Identifier: AGPL-3.0-or-later
"""The SFCM note types install with stable ids and render correctly (roadmap B01)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from anki.collection import Collection

from sfcm_engine.cards import GENERATABLE_NOTE_TYPES
from sfcm_engine.deck.notetypes import SPECS, notetype_id, scratch_collection, stable_id
from sfcm_engine.deck.themes import THEMES


def add(col: Collection, ntid: int, **fields: str) -> list[tuple[str, str]]:
    """Add a note and return (question, answer) text for each card it creates."""
    note = col.new_note(col.models.get(ntid))  # type: ignore[arg-type]
    for name, value in fields.items():
        note[name] = value
    deck = col.decks.id("Biology::Cells")
    assert deck is not None
    col.add_note(note, deck)
    return [(card.question(), card.answer()) for card in note.cards()]


def test_every_generatable_type_has_a_note_type() -> None:
    assert set(SPECS) == set(GENERATABLE_NOTE_TYPES)


def test_ids_are_stable_across_collections(tmp_path: Path) -> None:
    col_a, ids_a = scratch_collection(tmp_path / "a.anki2", "index")
    col_b, ids_b = scratch_collection(tmp_path / "b.anki2", "index")
    assert ids_a == ids_b
    for key, ntid in ids_a.items():
        nt_a, nt_b = col_a.models.get(ntid), col_b.models.get(ntid)
        assert nt_a and nt_b, key
        assert [f["id"] for f in nt_a["flds"]] == [f["id"] for f in nt_b["flds"]]
        assert [t["id"] for t in nt_a["tmpls"]] == [t["id"] for t in nt_b["tmpls"]]
        assert nt_a["name"].startswith("SFCM ")
    col_a.close()
    col_b.close()


def test_ids_differ_per_theme_and_never_collide() -> None:
    ids = {notetype_id(spec, theme) for spec in SPECS.values() for theme in THEMES.values()}
    assert len(ids) == len(SPECS) * len(THEMES)
    assert stable_id("a", "b") != stable_id("a", "c")


def test_basic_renders_extras_only_when_filled(tmp_path: Path) -> None:
    col, ids = scratch_collection(tmp_path / "c.anki2", "index")
    [(question, answer)] = add(
        col, ids["basic"], Front="Which organelle makes ATP?", Back="Mitochondrion", Why="Because."
    )
    assert "Which organelle makes ATP?" in question
    assert "Cells" in question  # {{Subdeck}} shows the last part of the deck name
    assert "Mitochondrion" not in question
    assert "Mitochondrion" in answer and "Because." in answer
    assert "Memory hook" not in answer  # empty field, section hidden
    col.close()


def test_reversed_types(tmp_path: Path) -> None:
    col, ids = scratch_collection(tmp_path / "c.anki2", "index")
    both = add(col, ids["basic_reversed"], Front="perro", Back="dog")
    assert len(both) == 2 and "dog" in both[1][0]
    one = add(col, ids["basic_optional_reversed"], Front="gato", Back="cat")
    two = add(col, ids["basic_optional_reversed"], Front="pez", Back="fish", **{"Add Reverse": "y"})
    assert (len(one), len(two)) == (1, 2)
    col.close()


def test_type_in_and_cloze(tmp_path: Path) -> None:
    col, ids = scratch_collection(tmp_path / "c.anki2", "index")
    [(question, _)] = add(col, ids["basic_type_in"], Front="Spanish for dog?", Back="perro")
    assert "typeans" in question
    cards = add(col, ids["cloze"], Text="ATP is made in {{c1::mitochondria}} using {{c2::oxygen}}.")
    assert len(cards) == 2
    question, answer = cards[0]
    visible = re.sub(r"<[^>]+>", "", question.split("</style>")[-1])
    assert "[...]" in visible and "mitochondria" not in visible
    assert "mitochondria" in answer
    col.close()


def test_theme_keys_match_the_protocol() -> None:
    from typing import get_args

    from sfcm_engine.protocol import ThemeKey

    assert set(get_args(ThemeKey)) == set(THEMES)


@pytest.mark.parametrize("theme_key", sorted(THEMES))
def test_every_theme_supports_night_mode_and_phones(theme_key: str) -> None:
    css = THEMES[theme_key].css
    assert ".card.nightMode" in css and ".card.night_mode" in css
    assert "@media (max-width: 480px)" in css


def test_themes_get_separate_note_types(tmp_path: Path) -> None:
    from sfcm_engine.deck.package import write_package

    from .test_package import CARDS, import_into

    user = Collection(str(tmp_path / "user.anki2"))
    for key in THEMES:
        import_into(user, write_package(CARDS[:1], tmp_path / f"{key}.apkg", theme=key).path)
    names = {nt.name for nt in user.models.all_names_and_ids() if nt.name.startswith("SFCM")}
    assert names == {f"SFCM Basic · {theme.name}" for theme in THEMES.values()}
    user.close()
