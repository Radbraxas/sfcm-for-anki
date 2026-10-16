# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2
import pytest

from sfcm_engine.prompts import PromptLibrary


def test_latest_card_prompt_renders_with_rubric() -> None:
    lib = PromptLibrary()
    prompt = lib.render(
        "card_generation",
        count=5,
        language="English",
        audience="a student",
        mix_instruction="any",
        extras_instruction="none",
        source_label="notes.md",
        source="The mitochondrion makes ATP. {{c1::not a template}}",
    )
    assert prompt.version.startswith("card_generation@")
    assert "One fact per card" in prompt.system
    assert "{{c1::mitochondria::organelle}}" in prompt.system  # rubric inserted verbatim
    assert "{{c1::not a template}}" in prompt.user  # source never parsed as a template
    assert "notes.md" in prompt.user


def test_system_prompt_is_stable_for_caching() -> None:
    lib = PromptLibrary()
    common: dict[str, Any] = dict(
        count=5, language="English", audience="a", mix_instruction="m", extras_instruction="e"
    )
    a = lib.render("card_generation", source_label="a", source="one", **common)
    b = lib.render("card_generation", source_label="b", source="two", **common)
    assert a.system == b.system


def test_missing_variable_fails_loudly() -> None:
    with pytest.raises(jinja2.UndefinedError):
        PromptLibrary().render("card_generation", count=3)


def test_versions_sort_semantically(tmp_path: Path) -> None:
    for v in ["1.2.0", "1.10.0", "1.9.3"]:
        (tmp_path / "p" / v).mkdir(parents=True)
        (tmp_path / "p" / v / "system.md.j2").write_text("s")
        (tmp_path / "p" / v / "user.md.j2").write_text("u")
    assert PromptLibrary(tmp_path).latest("p") == "1.10.0"
