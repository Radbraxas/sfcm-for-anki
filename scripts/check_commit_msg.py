# SPDX-License-Identifier: AGPL-3.0-or-later
"""commit-msg hook and CI check: Conventional Commit subject + DCO sign-off.

Usage: python3 scripts/check_commit_msg.py <message-file>
"""

import re
import sys

TYPES = "build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test"
SUBJECT = re.compile(rf"^({TYPES})(\([a-z0-9-]+\))?!?: \S.{{0,98}}$")
SIGNOFF = re.compile(r"^Signed-off-by: .+ <[^>]+@[^>]+>$", re.MULTILINE)


def check(message: str) -> list[str]:
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    subject = lines[0] if lines else ""
    problems = []
    if subject.startswith(("Merge ", 'Revert "')):
        return problems
    if not SUBJECT.match(subject):
        problems.append(
            f'subject "{subject}" is not a Conventional Commit, e.g. "feat(engine): add pdf parser"'
        )
    if not SIGNOFF.search("\n".join(lines)):
        problems.append("missing DCO sign-off; commit with `git commit -s`")
    return problems


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as f:
        problems = check(f.read())
    for problem in problems:
        print(f"commit message: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
