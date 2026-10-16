# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export the hand-written sample deck in every theme, for checking in real Anki apps.

    just sample-deck              # writes .sfcm-data/samples/SFCM sample (<theme>).apkg
    just sample-deck ~/Downloads  # or into another folder

The cards (sample_cards.json) cover every note type, the Why/Example/Mnemonic/Source
fields, math, code, multi-deletion cloze, and one card whose text contains script
tags to show the sanitizer at work. Import a file in Anki with File > Import.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sfcm_engine.cards import Card
from sfcm_engine.deck.package import write_package
from sfcm_engine.deck.themes import THEMES

HERE = Path(__file__).resolve().parent


def main() -> int:
    out_dir = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(".sfcm-data/samples")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = json.loads((HERE / "sample_cards.json").read_text(encoding="utf-8"))
    for theme in THEMES.values():
        # Theme-specific ids: the same card in another theme is the same note to Anki,
        # which refuses to move it to a different note type on import. Separate ids
        # let all three sample decks be imported side by side.
        cards = [Card.model_validate({**item, "id": f"{item['id']}-{theme.key}"}) for item in raw]
        path = out_dir / f"SFCM sample ({theme.name}).apkg"
        result = write_package(cards, path, deck_name=f"SFCM Sample::{theme.name}", theme=theme.key)
        print(f"{result.path}  ({result.notes} notes, {result.cards} cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
