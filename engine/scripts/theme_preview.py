# SPDX-License-Identifier: AGPL-3.0-or-later
"""Render every theme x note type x light/night mode into one HTML page (roadmap B05).

    just theme-preview            # writes .sfcm-data/theme-preview.html

Cards are rendered by Anki itself (card.question()/answer()), then shown in iframes
with the classes Anki puts on the page (`card`, plus `nightMode night_mode` in night
mode), at desktop and phone widths. Use it to check a theme change before release.
"""

from __future__ import annotations

import html
import sys
import tempfile
from pathlib import Path

from sfcm_engine.cards import Card
from sfcm_engine.deck.notetypes import scratch_collection
from sfcm_engine.deck.package import note_fields
from sfcm_engine.deck.themes import THEMES


def sample(note_type: str, **fields: str) -> Card:
    base = {
        "id": note_type,
        "note_type": note_type,
        "front": "",
        "back": "",
        "text": "",
        "why": "The inner membrane carries the electron transport chain and **ATP synthase**.",
        "example": "Cyanide blocks complex IV, so cells starve of ATP even with oxygen present.",
        "mnemonic": "Mito = the cell's **power plant**.",
        "tags": ["cell-biology"],
        "source": "Lecture 4 · Cellular respiration",
        "prompt_version": "preview",
        "model": "preview",
    }
    base.update(fields)
    return Card(**base)  # pyright: ignore[reportArgumentType]


SAMPLES = [
    sample(
        "basic", front="Which organelle makes most of a cell's **ATP**?", back="The mitochondrion"
    ),
    sample(
        "cloze",
        text="ATP synthase is driven by the {{c1::proton gradient}} across the inner membrane.",
        mnemonic="",
    ),
    sample("basic_type_in", front="Spanish for *dog*?", back="perro", example="", mnemonic=""),
]


def frame(body: str, night: bool, width: int) -> str:
    classes = "card card1" + (" nightMode night_mode" if night else "")
    doc = f'<!doctype html><html><body class="{classes}">{body}</body></html>'
    return (
        f'<iframe width="{width}" height="520" style="border:1px solid #ccc;border-radius:8px" '
        f'srcdoc="{html.escape(doc)}"></iframe>'
    )


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".sfcm-data/theme-preview.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for theme in THEMES.values():
            col, ids = scratch_collection(Path(tmp) / f"{theme.key}.anki2", theme.key)
            deck = col.decks.id("Biology::Mitochondria")
            assert deck is not None
            for card in SAMPLES:
                notetype = col.models.get(ids[card.note_type])
                assert notetype is not None
                note = col.new_note(notetype)
                for name, value in note_fields(card).items():
                    note[name] = value
                col.add_note(note, deck)
                rendered = note.cards()[0]
                cells = [
                    frame(rendered.question(), night=False, width=420),
                    frame(rendered.answer(), night=False, width=420),
                    frame(rendered.answer(), night=True, width=420),
                    frame(rendered.answer(), night=False, width=360),
                ]
                rows.append(
                    f"<h2>{theme.name} · {card.note_type}</h2>"
                    f'<div style="display:flex;gap:12px;flex-wrap:wrap">{"".join(cells)}</div>'
                )
            col.close()
    out.write_text(
        "<!doctype html><meta charset=utf-8><title>SFCM theme preview</title>"
        "<body style='font-family:system-ui;margin:24px'>"
        "<p>Columns: front · back · back in night mode · back at phone width.</p>" + "".join(rows),
        encoding="utf-8",
    )
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
