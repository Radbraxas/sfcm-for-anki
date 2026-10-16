# SPDX-License-Identifier: AGPL-3.0-or-later
"""Entry point for the PyInstaller bundle (a package's __main__ can't be frozen directly)."""

import sys

from sfcm_engine.__main__ import main

sys.exit(main())
