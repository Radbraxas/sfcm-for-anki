# SPDX-License-Identifier: AGPL-3.0-or-later
"""Card-quality metrics (roadmap A11). Pure functions, so they are unit-tested."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from sfcm_engine.cards import GeneratedCard
from sfcm_engine.quality.lint import lint_card

DUPLICATE_THRESHOLD = 0.8
REGRESSION_TOLERANCE = 0.05  # flag a drop of more than 5% (relative)

# metric -> True when higher is better
TRACKED: dict[str, bool] = {
    "schema_validity": True,
    "lint_pass_rate": True,
    "faithfulness": True,
    "atomicity": True,
    "clarity": True,
    "duplicate_rate": False,
}


@dataclass
class SourceResult:
    source: str
    accepted: int
    rejected: int
    lint_clean: int
    duplicates: int
    judge: dict[str, float]  # mean 1-5 score per criterion
    cost_usd: float | None
    notes: list[str] = field(default_factory=lambda: [])


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def card_text(card: GeneratedCard) -> str:
    return card.text if card.note_type == "cloze" else f"{card.front} {card.back}"


def jaccard(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def count_duplicates(cards: Sequence[GeneratedCard], threshold: float = DUPLICATE_THRESHOLD) -> int:
    """Cards that are near-copies of an earlier card (word-set Jaccard >= threshold)."""
    texts = [card_text(c) for c in cards]
    dupes = 0
    for i, text in enumerate(texts):
        if any(jaccard(text, earlier) >= threshold for earlier in texts[:i]):
            dupes += 1
    return dupes


def count_lint_clean(cards: Iterable[GeneratedCard]) -> int:
    return sum(1 for c in cards if not lint_card(c))


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(results: Sequence[SourceResult]) -> dict[str, float]:
    accepted = sum(r.accepted for r in results)
    generated = accepted + sum(r.rejected for r in results)
    weighted = lambda key: (  # noqa: E731
        sum(r.judge.get(key, 0.0) * r.accepted for r in results) / accepted if accepted else 0.0
    )
    costs = [r.cost_usd for r in results if r.cost_usd is not None]
    return {
        "cards": float(accepted),
        "schema_validity": accepted / generated if generated else 0.0,
        "lint_pass_rate": sum(r.lint_clean for r in results) / accepted if accepted else 0.0,
        "duplicate_rate": sum(r.duplicates for r in results) / accepted if accepted else 0.0,
        "faithfulness": weighted("faithfulness"),
        "atomicity": weighted("atomicity"),
        "clarity": weighted("clarity"),
        "cost_per_accepted_card_usd": (sum(costs) / accepted) if costs and accepted else -1.0,
    }


def regressions(
    baseline: dict[str, float],
    current: dict[str, float],
    tolerance: float = REGRESSION_TOLERANCE,
) -> list[str]:
    """Human-readable lines for every tracked metric that got worse by more than tolerance."""
    found: list[str] = []
    for metric, higher_is_better in TRACKED.items():
        if metric not in baseline or metric not in current:
            continue
        old, new = baseline[metric], current[metric]
        if higher_is_better:
            worse = old > 0 and (old - new) / old > tolerance
        else:
            worse = new - old > tolerance  # rates near zero: compare absolute change
        if worse:
            found.append(f"{metric}: {old:.3f} -> {new:.3f}")
    return found


def render_markdown(
    summary: dict[str, float],
    results: Sequence[SourceResult],
    meta: dict[str, Any],
    baseline: dict[str, float] | None,
    regressed: list[str],
) -> str:
    lines = [
        "## Card quality eval",
        "",
        f"Generator `{meta['model']}` with prompt `{meta['prompt_version']}`, "
        f"judged by `{meta['judge_model']}`, {meta['count']} cards per source.",
        "",
        "| Metric | Baseline | This run |",
        "|---|---|---|",
    ]
    for key, value in summary.items():
        old = f"{baseline[key]:.3f}" if baseline and key in baseline else "n/a"
        lines.append(f"| {key} | {old} | {value:.3f} |")
    lines += [
        "",
        "| Source | Accepted | Rejected | Lint clean | Duplicates |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.source} | {r.accepted} | {r.rejected} | {r.lint_clean} | {r.duplicates} |"
        )
    lines.append("")
    if regressed:
        lines += [
            "**Regressions (over 5%):**",
            "",
            *[f"- {line}" for line in regressed],
        ]
    else:
        lines.append("No regressions against the baseline.")
    return "\n".join(lines) + "\n"


def to_json(results: Sequence[SourceResult]) -> list[dict[str, Any]]:
    return [asdict(r) for r in results]
