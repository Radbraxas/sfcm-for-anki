# SPDX-License-Identifier: AGPL-3.0-or-later
"""Strip anything executable from HTML before it goes into an Anki field (roadmap B08).

Anki renders fields as HTML in a web view and runs any JavaScript it finds there, on
desktop and on phones. Card text can come from an AI model reading untrusted
documents, from imported decks, and later from the rich editor, so every field the
app writes passes through `sanitize_html`, whatever produced it.

Allowed: basic formatting, lists, tables, ruby (furigana), and images that point at
media files inside the package. Not allowed: scripts, event handlers, styles, iframes,
SVG, forms, links, and any absolute or `data:` URL.
"""

from __future__ import annotations

import nh3

ALLOWED_TAGS = frozenset(
    {
        "b", "strong", "i", "em", "u", "s", "sub", "sup", "mark", "small",
        "code", "pre", "kbd", "br", "hr", "p", "div", "span", "blockquote",
        "ul", "ol", "li", "dl", "dt", "dd",
        "table", "thead", "tbody", "tr", "th", "td",
        "ruby", "rt", "rp", "img",
    }
)  # fmt: skip

ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}

# Tags removed together with everything inside them, not just unwrapped.
REMOVE_WITH_CONTENT = frozenset({"script", "style", "iframe", "object", "embed", "svg", "math"})


def sanitize_html(html: str) -> str:
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        clean_content_tags=set(REMOVE_WITH_CONTENT),
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=set(),  # only relative URLs, i.e. media files in the package
        strip_comments=True,
        link_rel=None,
    )
