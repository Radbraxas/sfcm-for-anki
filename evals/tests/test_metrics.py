# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from typing import Any

import pytest

from evals.metrics import (
    SourceResult,
    aggregate,
    count_duplicates,
    jaccard,
    regressions,
    render_markdown,
)
from sfcm_engine.cards import GeneratedCard


def card(front: str, back: str = "an answer") -> GeneratedCard:
    return GeneratedCard(
        note_type="basic",
        front=front,
        back=back,
        text="",
        why="",
        example="",
        mnemonic="",
        tags=["t"],
    )


def test_jaccard() -> None:
    assert jaccard("the cell wall", "The cell wall!") == 1.0
    assert jaccard("", "anything") == 0.0


def test_near_copies_count_as_duplicates() -> None:
    cards = [
        card("Which organelle makes ATP?", "mitochondrion"),
        card("Which organelle makes ATP", "the mitochondrion"),
        card("What does chlorophyll absorb?", "red and blue light"),
    ]
    assert count_duplicates(cards) == 1


def result(**kw: Any) -> SourceResult:
    base: dict[str, Any] = dict(
        source="s.md",
        accepted=8,
        rejected=2,
        lint_clean=6,
        duplicates=1,
        judge={"faithfulness": 4.5, "atomicity": 4.0, "clarity": 3.5},
        cost_usd=0.08,
    )
    base.update(kw)
    return SourceResult(**base)


def test_aggregate() -> None:
    summary = aggregate([result(), result(accepted=2, rejected=0, lint_clean=2, duplicates=0)])
    assert summary["cards"] == 10
    assert summary["schema_validity"] == pytest.approx(10 / 12)
    assert summary["lint_pass_rate"] == pytest.approx(8 / 10)
    assert summary["faithfulness"] == pytest.approx(4.5)
    assert summary["cost_per_accepted_card_usd"] == pytest.approx(0.016)


def test_regressions_respect_direction_and_tolerance() -> None:
    base = {"faithfulness": 4.0, "clarity": 4.0, "duplicate_rate": 0.02}
    assert regressions(base, {"faithfulness": 3.9, "clarity": 4.0, "duplicate_rate": 0.02}) == []
    found = regressions(base, {"faithfulness": 3.7, "clarity": 4.4, "duplicate_rate": 0.10})
    assert [line.split(":")[0] for line in found] == ["faithfulness", "duplicate_rate"]


def test_markdown_report_mentions_regressions() -> None:
    meta = {"model": "m", "prompt_version": "p@1", "judge_model": "j", "count": 5}
    text = render_markdown(aggregate([result()]), [result()], meta, None, ["clarity: 4 -> 3"])
    assert "| faithfulness | n/a |" in text
    assert "- clarity: 4 -> 3" in text
