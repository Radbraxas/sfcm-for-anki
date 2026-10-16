# SPDX-License-Identifier: AGPL-3.0-or-later
"""The engine's SQLite database: settings now; sessions, jobs and manifests later (A08).

Migrations are numbered `NNNN_name.sql` files in `migrations/`, applied in order and
recorded in `schema_migrations`. Never edit a migration that has shipped; add a new one.
"""

from __future__ import annotations

import json
import re
import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any

_MIGRATION_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def available_migrations() -> list[tuple[int, str, str]]:
    """(version, filename, sql) for every bundled migration, in order."""
    found: list[tuple[int, str, str]] = []
    for entry in resources.files("sfcm_engine.migrations").iterdir():
        match = _MIGRATION_RE.match(entry.name)
        if match:
            found.append((int(match.group(1)), entry.name, entry.read_text(encoding="utf-8")))
    found.sort()
    versions = [v for v, _, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError(f"migration numbers must be 1..n without gaps, got {versions}")
    return found


class Database:
    def __init__(self, path: Path | str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")

    def close(self) -> None:
        self.conn.close()

    def schema_version(self) -> int:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        row = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)

    def migrate(self, target: int | None = None) -> int:
        """Apply pending migrations up to `target` (default: latest). Returns the new version."""
        current = self.schema_version()
        for version, name, sql in available_migrations():
            if version <= current or (target is not None and version > target):
                continue
            # One transaction per file, including its bookkeeping row. `name` is safe to
            # inline: it matched _MIGRATION_RE.
            self.conn.executescript(
                f"BEGIN;\n{sql}\n"
                f"INSERT INTO schema_migrations (version, name) VALUES ({version}, '{name}');\n"
                "COMMIT;"
            )
            current = version
        return current

    # --- settings ------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def set_setting(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
            " updated_at = datetime('now')",
            (key, json.dumps(value)),
        )
