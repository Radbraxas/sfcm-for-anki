# SPDX-License-Identifier: AGPL-3.0-or-later
"""Smoke test for the pinned `anki` package (roadmap A15).

Exports a one-note package and imports it into a fresh collection, in both the modern
and the legacy format. The weekly anki-compat workflow runs this against the newest
Anki release before the pin is bumped.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

import pytest
from anki.collection import (
    Collection,
    DeckIdLimit,
    ExportAnkiPackageOptions,
    ImportAnkiPackageOptions,
    ImportAnkiPackageRequest,
)


def test_anki_package_is_installed() -> None:
    assert metadata.version("anki")


@pytest.mark.parametrize("legacy", [False, True])
def test_export_import_round_trip(tmp_path: Path, legacy: bool) -> None:
    src = Collection(str(tmp_path / "src.anki2"))
    deck_id = src.decks.id("SFCM::Smoke")
    assert deck_id is not None
    note = src.new_note(src.models.by_name("Basic"))  # type: ignore[arg-type]
    note["Front"] = "Which organelle makes most ATP?"
    note["Back"] = "The mitochondrion"
    src.add_note(note, deck_id)
    package = tmp_path / "smoke.apkg"
    exported = src.export_anki_package(
        out_path=str(package),
        options=ExportAnkiPackageOptions(
            with_scheduling=False, with_deck_configs=False, with_media=True, legacy=legacy
        ),
        limit=DeckIdLimit(deck_id),
    )
    src.close()
    assert exported == 1

    dst = Collection(str(tmp_path / "dst.anki2"))
    result = dst.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=str(package), options=ImportAnkiPackageOptions(with_scheduling=False)
        )
    )
    assert len(result.log.new) == 1
    imported = dst.get_note(dst.find_notes("deck:SFCM::Smoke")[0])
    assert imported["Back"] == "The mitochondrion"
    dst.close()
