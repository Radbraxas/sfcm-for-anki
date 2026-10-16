# SPDX-License-Identifier: AGPL-3.0-or-later
"""Card templates for the SFCM note types (roadmap B01).

Templates only carry structure and class names. How cards look is the note type's
CSS, which comes from a theme (themes.py), so the same templates serve every theme.
`{{Subdeck}}` is Anki's built-in "last part of the deck name" field.
"""

from __future__ import annotations


def eyebrow(kind: str) -> str:
    return (
        '<div class="sfcm-eyebrow">'
        '<span class="sfcm-deck">{{Subdeck}}</span>'
        f'<span class="sfcm-kind">{kind}</span>'
        "</div>"
    )


# Shown under the answer on every type. Each block disappears when its field is empty.
EXTRAS = (
    '<div class="sfcm-extras">'
    '{{#Why}}<section class="sfcm-extra"><h4>Why</h4><div>{{Why}}</div></section>{{/Why}}'
    "{{#Example}}"
    '<section class="sfcm-extra"><h4>Example</h4><div>{{Example}}</div></section>'
    "{{/Example}}"
    "{{#Mnemonic}}"
    '<section class="sfcm-extra sfcm-hook"><h4>Memory hook</h4><div>{{Mnemonic}}</div></section>'
    "{{/Mnemonic}}"
    "</div>"
    '{{#Source}}<footer class="sfcm-source">{{Source}}</footer>{{/Source}}'
)


def front(prompt_field: str, kind: str, extra: str = "") -> str:
    return (
        f'<div class="sfcm sfcm-front">{eyebrow(kind)}'
        f'<div class="sfcm-prompt">{{{{{prompt_field}}}}}</div>{extra}</div>'
    )


def back(answer_field: str) -> str:
    return (
        "{{FrontSide}}"
        '<hr id="answer">'
        f'<div class="sfcm sfcm-back"><div class="sfcm-answer">{{{{{answer_field}}}}}</div>'
        f"{EXTRAS}</div>"
    )


TYPE_IN_FRONT = front("Front", "Type the answer", extra="{{type:Back}}")
TYPE_IN_BACK = (
    '<div class="sfcm sfcm-front">'
    + eyebrow("Type the answer")
    + '<div class="sfcm-prompt">{{Front}}</div></div>'
    '<hr id="answer">'
    '<div class="sfcm sfcm-back">{{type:Back}}' + EXTRAS + "</div>"
)

CLOZE_FRONT = (
    '<div class="sfcm sfcm-front sfcm-cloze">'
    + eyebrow("Fill in")
    + '<div class="sfcm-prompt">{{cloze:Text}}</div></div>'
)
CLOZE_BACK = (
    '<div class="sfcm sfcm-front sfcm-cloze">'
    + eyebrow("Fill in")
    + '<div class="sfcm-prompt">{{cloze:Text}}</div></div>'
    '<div class="sfcm sfcm-back">' + EXTRAS + "</div>"
)
