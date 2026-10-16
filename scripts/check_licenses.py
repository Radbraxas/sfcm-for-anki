# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail if a Python or JavaScript dependency has a license incompatible with AGPL-3.0.

Rust crates are checked separately by cargo-deny (deny.toml).
Usage: just licenses
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from typing import Any

# SPDX ids (or common spellings of them) that may be combined with AGPL-3.0-or-later.
ALLOWED = {
    "MIT",
    "MIT-0",
    "ISC",
    "0BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "Apache-2.0",
    "Zlib",
    "Unlicense",
    "CC0-1.0",
    "PSF-2.0",
    "Python-2.0",
    "MPL-2.0",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "BlueOak-1.0.0",
    "Unicode-3.0",
    "CC-BY-4.0",
}
# Classifier-style names pip reports, mapped to SPDX.
ALIASES = {
    "MIT License": "MIT",
    "BSD License": "BSD-3-Clause",
    "BSD": "BSD-3-Clause",
    "3-Clause BSD License": "BSD-3-Clause",
    "Apache Software License": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Python Software Foundation License": "PSF-2.0",
    "ISC License (ISCL)": "ISC",
    "The Unlicense (Unlicense)": "Unlicense",
    "GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
    "GNU Library or Lesser General Public License (LGPL)": "LGPL-2.1-or-later",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1-or-later",
    "GNU Affero General Public License v3": "AGPL-3.0-only",
    "GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0-or-later",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
}
# Packages reviewed by hand, with the reason.
REVIEWED = {
    "pyinstaller": "GPL-2.0-or-later with a bootloader exception; build tool, output not covered",
    "pyinstaller-hooks-contrib": "GPL-2.0-or-later / Apache-2.0; build tool only",
    "sfcm-engine": "this project",
}


def acceptable(expression: str) -> bool:
    """True if any alternative of an SPDX-ish expression ("MIT OR Apache-2.0") is allowed."""
    if ALIASES.get(expression.strip(), expression.strip()) in ALLOWED:
        return True
    parts = re.split(r"\s+OR\s+|\s*;\s*|\s*/\s*", expression.strip("() "))
    for part in parts:
        part = ALIASES.get(part.strip(), part.strip())
        if part in ALLOWED:
            return True
        # "A AND B" needs every term allowed
        terms = [ALIASES.get(t.strip("() "), t.strip("() ")) for t in re.split(r"\s+AND\s+", part)]
        if len(terms) > 1 and all(t in ALLOWED for t in terms):
            return True
    return False


def python_packages() -> list[tuple[str, str]]:
    out = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json", "--from=mixed"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [(p["Name"], p["License"]) for p in json.loads(out)]


def js_packages() -> list[tuple[str, str]]:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        print("pnpm not found; skipping JavaScript packages", file=sys.stderr)
        return []
    out = subprocess.run(
        [pnpm, "licenses", "list", "--prod", "--json"], capture_output=True, text=True, check=True
    ).stdout
    data: dict[str, list[dict[str, Any]]] = json.loads(out or "{}")
    return [(pkg["name"], license_id) for license_id, pkgs in data.items() for pkg in pkgs]


def main() -> int:
    bad = [
        (ecosystem, name, lic)
        for ecosystem, packages in (("python", python_packages()), ("npm", js_packages()))
        for name, lic in packages
        if name.lower() not in REVIEWED and not acceptable(lic)
    ]
    for ecosystem, name, lic in sorted(bad):
        print(f"{ecosystem}: {name}: {lic!r} is not on the allow list", file=sys.stderr)
    if bad:
        print(
            "\nAdd a compatible license to ALLOWED/ALIASES, or review the package and add it "
            "to REVIEWED with a reason.",
            file=sys.stderr,
        )
        return 1
    print("All Python and JavaScript dependency licenses are compatible with AGPL-3.0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
