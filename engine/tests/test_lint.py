# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from sfcm_engine.quality.lint import has_errors, lint_card, normalize_tags

from .conftest import card


def rules(**overrides: object) -> set[str]:
    return {i.rule for i in lint_card(card(**overrides))}


def test_good_card_has_no_issues() -> None:
    assert lint_card(card()) == []


def test_cloze_without_deletion_is_an_error() -> None:
    issues = lint_card(card(note_type="cloze", front="", back="", text="No deletion here."))
    assert has_errors(issues)


def test_cloze_with_hint_is_fine() -> None:
    assert (
        lint_card(
            card(
                note_type="cloze",
                front="",
                back="",
                text="ATP is made in {{c1::mitochondria::organelle}}.",
            )
        )
        == []
    )


def test_warnings() -> None:
    assert "yes_no_question" in rules(front="Is ATP made in mitochondria?")
    assert "long_answer" in rules(back=" ".join(["word"] * 16))
    assert "possible_list" in rules(back="glucose, oxygen, water")


def test_html_is_an_error() -> None:
    assert has_errors(lint_card(card(why="<script>alert(1)</script>")))


def test_normalize_tags() -> None:
    assert normalize_tags(["Cell Biology", "cell-biology", " ATP!"]) == ["cell-biology", "atp"]
