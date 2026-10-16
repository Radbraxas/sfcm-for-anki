# SPDX-License-Identifier: AGPL-3.0-or-later
"""Turn card text into Anki field HTML.

Card text uses a small Markdown subset (**bold**, *italic*, `code`, line breaks).
Everything else is escaped, so text can never inject markup into a card. Cloze
markers ({{c1::...}}) and MathJax delimiters (\\( \\)) pass through unchanged.
"""

from __future__ import annotations

import html
import re

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])")


def to_html(text: str) -> str:
    escaped = html.escape(text.strip(), quote=False)
    # Code first, so * inside code stays literal.
    parts = _CODE.split(escaped)
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f"<code>{part}</code>")
        else:
            part = _BOLD.sub(r"<b>\1</b>", part)
            out.append(_ITALIC.sub(r"<i>\1</i>", part))
    return "".join(out).replace("\r\n", "\n").replace("\n", "<br>")
