# SPDX-License-Identifier: AGPL-3.0-or-later
"""No script can reach an Anki field (roadmap B08)."""

from __future__ import annotations

import random
import re
from html.parser import HTMLParser

import pytest

from sfcm_engine.deck.fields import to_html
from sfcm_engine.deck.sanitize import ALLOWED_TAGS, sanitize_html

VECTORS = [
    "<script>alert(1)</script>",
    "<SCRIPT SRC=//evil.example/x.js></SCRIPT>",
    "<img src=x onerror=alert(1)>",
    "<img src=x OnErRoR=alert(1)>",
    '<img src="javascript:alert(1)">',
    '<img src="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">',
    "<svg onload=alert(1)><script>alert(2)</script></svg>",
    "<iframe srcdoc='<script>alert(1)</script>'></iframe>",
    "<a href=javascript:alert(1)>click</a>",
    '<div style="background:url(javascript:alert(1))">x</div>',
    "<style>*{display:none}</style>",
    "<body onload=alert(1)>",
    "<math><mi xlink:href=javascript:alert(1)>x</mi></math>",
    "<details open ontoggle=alert(1)>",
    "<object data=javascript:alert(1)>",
    "<form action=javascript:alert(1)><button>x</button></form>",
    "<input autofocus onfocus=alert(1)>",
    "<<script>script>alert(1)<</script>/script>",
    "<scr<script>ipt>alert(1)</script>",
    "<!--<script>alert(1)</script>-->",
    "<img src=`x` onerror=alert(1)>",
    "<b onmouseover=alert(1)>hover</b>",
]


class TagAudit(HTMLParser):
    """Collects every real tag and attribute in a fragment (escaped text is not a tag)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problems: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            self.problems.append(f"tag <{tag}>")
        for name, value in attrs:
            if name.startswith("on") or name in {"style", "srcdoc", "href", "action"}:
                self.problems.append(f"attribute {name}")
            if value and re.match(r"\s*(javascript|data|vbscript):", value, re.IGNORECASE):
                self.problems.append(f"url {value}")
            if name == "src" and value and re.match(r"\s*[a-z][a-z0-9+.-]*:|//", value, re.I):
                self.problems.append(f"absolute src {value}")

    def handle_comment(self, data: str) -> None:
        self.problems.append("comment")


def audit(fragment: str) -> list[str]:
    parser = TagAudit()
    parser.feed(fragment)
    parser.close()
    return parser.problems


@pytest.mark.parametrize("vector", VECTORS)
def test_known_vectors_are_neutralized(vector: str) -> None:
    assert audit(sanitize_html(vector)) == [], sanitize_html(vector)
    # Model text goes through to_html first, which escapes it into plain text.
    assert audit(sanitize_html(to_html(vector))) == []


def test_random_fragments_never_produce_unsafe_markup() -> None:
    fragments = [
        "<", ">", "/", "script", "img", "svg", " src=x", " onerror=", "alert(1)", '"', "'",
        "javascript:", "<b>", "</b>", "**", "`", "{{c1::", "}}", "\\(", "\\)", "\n", "&", "#",
        "<!--", "-->", " style=", "data:", "on", "load", "=", "iframe", " ", "<img", "<a ",
    ]  # fmt: skip
    rng = random.Random(1234)
    for _ in range(5000):
        text = "".join(rng.choice(fragments) for _ in range(rng.randint(1, 25)))
        for out in (sanitize_html(text), sanitize_html(to_html(text))):
            assert audit(out) == [], (text, out)


@pytest.mark.parametrize(
    "safe",
    [
        "<b>bold</b> <i>it</i> <code>x*y</code><br>line",
        "{{c1::mitochondria::organelle}} make ATP",
        r"\(E = mc^2\) and \[a^2 + b^2\]",
        '<img src="diagram.png" alt="Krebs cycle">',
        "<ruby>漢<rt>かん</rt></ruby>",
        '<table><tr><td colspan="2">x</td></tr></table>',
    ],
)
def test_legitimate_markup_survives(safe: str) -> None:
    out = sanitize_html(safe)
    assert out == sanitize_html(out)  # stable
    for token in ("{{c1::", r"\(", "diagram.png", "<b>", "<ruby>", "colspan"):
        if token in safe:
            assert token in out


def test_to_html_output_is_already_clean() -> None:
    text = "Use **ATP** and `code` with x < y & z\nnext line"
    assert sanitize_html(to_html(text)) == to_html(text)
