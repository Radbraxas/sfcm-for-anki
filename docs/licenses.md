# Licensing

SFCM for Anki is licensed under AGPL-3.0-or-later (see `LICENSE`), because the engine links the official `anki` Python package, which is AGPL-3.0.

## Dependency policy

Every dependency must be compatible with AGPL-3.0-or-later. Allowed: MIT, ISC, BSD-2/3-Clause, Apache-2.0, Zlib, MPL-2.0, LGPL, GPL-3.0, AGPL-3.0, CC0, Unlicense, PSF, Unicode. Not allowed: GPL-2.0-only, proprietary or "non-commercial" licenses.

CI enforces this:

- Rust: `cargo deny check licenses` with `deny.toml`
- Python and JavaScript: `just licenses` (`scripts/check_licenses.py`)

Build-only tools that never ship in the app (PyInstaller) are reviewed by hand and listed with a reason in `scripts/check_licenses.py`.

## Source headers

Every source file starts with `SPDX-License-Identifier: AGPL-3.0-or-later` in a comment.

## Trademark

Anki is a trademark of Ankitects Pty Ltd. This project is not affiliated with or endorsed by Anki or Ankitects; the name "SFCM for Anki" only describes compatibility.

## Contributions

Contributions are accepted under the project license with a Developer Certificate of Origin sign-off (`git commit -s`), not a CLA. See `CONTRIBUTING.md`.
