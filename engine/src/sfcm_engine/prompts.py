# SPDX-License-Identifier: AGPL-3.0-or-later
"""Versioned prompt templates (roadmap A10).

Layout:  prompts/<name>/<semver>/system.md.j2 and user.md.j2,  prompts/shared/*.md
Shared files are inserted verbatim as `shared.<stem>` (they contain literal {{c1::...}}
cloze syntax, so they are never parsed as templates).
Every rendered prompt carries its version, and every card records the version that
produced it. Never edit a released version in place: copy it to a new version folder
and note the change in prompts/CHANGELOG.md.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2


def default_prompts_dir() -> Path:
    if env := os.environ.get("SFCM_PROMPTS_DIR"):
        return Path(env)
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return Path(getattr(sys, "_MEIPASS", ".")) / "prompts"
    # Source checkout: engine/src/sfcm_engine/prompts.py -> repo root
    return Path(__file__).resolve().parents[3] / "prompts"


def _semver_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: str
    system: str
    user: str


class PromptLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_prompts_dir()
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.root),
            undefined=jinja2.StrictUndefined,
            autoescape=False,  # noqa: S701 - plain-text prompts, never rendered as HTML
            keep_trailing_newline=True,
        )

    def versions(self, name: str) -> list[str]:
        folder = self.root / name
        if not folder.is_dir():
            raise FileNotFoundError(f"no prompt named {name!r} in {self.root}")
        found = [p.name for p in folder.iterdir() if p.is_dir() and (p / "system.md.j2").exists()]
        return sorted(found, key=_semver_key)

    def latest(self, name: str) -> str:
        versions = self.versions(name)
        if not versions:
            raise FileNotFoundError(f"prompt {name!r} has no versions")
        return versions[-1]

    def shared(self) -> dict[str, str]:
        folder = self.root / "shared"
        if not folder.is_dir():
            return {}
        return {p.stem: p.read_text(encoding="utf-8").strip() for p in folder.glob("*.md")}

    def render(self, name: str, version: str | None = None, **variables: Any) -> RenderedPrompt:
        version = version or self.latest(name)
        variables = {"shared": self.shared(), **variables}
        system = self._env.get_template(f"{name}/{version}/system.md.j2").render(**variables)
        user = self._env.get_template(f"{name}/{version}/user.md.j2").render(**variables)
        return RenderedPrompt(name=name, version=f"{name}@{version}", system=system, user=user)
