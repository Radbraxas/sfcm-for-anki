# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create or update the repository's labels from .github/labels.yml (needs the gh CLI)."""

import re
import subprocess
import sys
from pathlib import Path

LINE = re.compile(r'name: "([^"]+)", color: "([0-9a-f]{6})", description: "([^"]*)"')


def main() -> int:
    text = Path(__file__).resolve().parents[1].joinpath(".github/labels.yml").read_text()
    for name, color, description in LINE.findall(text):
        subprocess.run(
            [
                "gh",
                "label",
                "create",
                name,
                "--color",
                color,
                "--description",
                description,
                "--force",
            ],
            check=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
