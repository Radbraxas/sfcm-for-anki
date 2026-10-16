# SPDX-License-Identifier: AGPL-3.0-or-later
"""Card themes: the CSS stored on each SFCM note type (roadmap B01, B05).

Every theme gets its own set of note types (see notetypes.py), so decks in different
themes can live side by side in one collection without restyling each other.
A theme's CSS is its variables file (css/<key>.css) followed by css/base.css.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


def _css(name: str) -> str:
    return resources.files("sfcm_engine.deck").joinpath("css", name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Theme:
    key: str
    slot: int  # never reuse or renumber: it is part of the note type ids
    name: str

    @property
    def css(self) -> str:
        return _css(f"{self.key}.css") + _css("base.css")


THEMES: dict[str, Theme] = {
    "index": Theme("index", 0, "Index card"),
    "night": Theme("night", 1, "Night"),
    "signal": Theme("signal", 2, "Signal"),
}
