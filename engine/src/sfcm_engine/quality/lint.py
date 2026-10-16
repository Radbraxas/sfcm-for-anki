# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rule-based card checks: cheap, deterministic, no model call.

Used to drop broken cards after generation, by the eval harness (A11), and later by
the deck analyzer (E02). Errors make a card unusable; warnings only lower its score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ..cards import GeneratedCard

CLOZE_RE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.*?))?\}\}", re.DOTALL)
HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
YES_NO_RE = re.compile(
    r"^(is|are|was|were|does|do|did|can|could|should|will|would|has|have|had)\b", re.IGNORECASE
)
MAX_ANSWER_WORDS = 15

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    rule: str
    severity: Severity
    message: str


def lint_card(card: GeneratedCard) -> list[Issue]:
    issues: list[Issue] = []

    def add(rule: str, severity: Severity, message: str) -> None:
        issues.append(Issue(rule, severity, message))

    if card.note_type == "cloze":
        if not CLOZE_RE.search(card.text):
            add("cloze_missing_deletion", "error", "cloze text has no {{c1::...}} deletion")
        if card.front or card.back:
            add("cloze_has_front_back", "warning", "cloze cards should leave front/back empty")
    else:
        if not card.front.strip():
            add("missing_front", "error", "question is empty")
        if not card.back.strip():
            add("missing_back", "error", "answer is empty")
        if card.text.strip():
            add("text_on_non_cloze", "warning", "text is only used by cloze cards")
        if YES_NO_RE.match(card.front.strip()):
            add("yes_no_question", "warning", "yes/no questions are easy to guess")
        if len(card.back.split()) > MAX_ANSWER_WORDS:
            add("long_answer", "warning", f"answer is over {MAX_ANSWER_WORDS} words")
        if card.back.count(",") >= 2 or re.search(r"\b\d\)\s", card.back):
            add("possible_list", "warning", "answer looks like a list; consider splitting")

    for field_name in ("front", "back", "text", "why", "example", "mnemonic"):
        if HTML_TAG_RE.search(getattr(card, field_name)):
            add("html_in_field", "error", f"{field_name} contains HTML")

    if not 1 <= len(card.tags) <= 3:
        add("tag_count", "warning", "expected 1-3 tags")
    return issues


def has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == "error" for i in issues)


def normalize_tags(tags: list[str]) -> list[str]:
    """Anki tags cannot contain spaces; keep them lowercase and hyphenated."""
    seen: list[str] = []
    for tag in tags:
        clean = re.sub(r"[^a-z0-9:_\-]+", "-", tag.strip().lower()).strip("-")
        if clean and clean not in seen:
            seen.append(clean)
    return seen
