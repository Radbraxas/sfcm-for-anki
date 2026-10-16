# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

from sfcm_engine.db import Database, available_migrations


def test_fresh_database_reaches_latest() -> None:
    db = Database(":memory:")
    assert db.migrate() == len(available_migrations())
    assert db.migrate() == len(available_migrations())  # idempotent


def test_upgrade_from_every_previous_version(tmp_path: Path) -> None:
    latest = len(available_migrations())
    for start in range(latest + 1):
        db = Database(tmp_path / f"v{start}.sqlite3")
        db.migrate(target=start)
        assert db.schema_version() == start
        if start >= 1:
            db.set_setting("llm.provider", "ollama")
        assert db.migrate() == latest
        if start >= 1:
            assert db.get_setting("llm.provider") == "ollama"
        db.close()


def test_settings_round_trip_json(db: Database) -> None:
    assert db.get_setting("missing", "fallback") == "fallback"
    db.set_setting("ui.deck", {"name": "Bio::Cells", "count": 3})
    db.set_setting("ui.deck", {"name": "Bio::Cells", "count": 4})
    assert db.get_setting("ui.deck") == {"name": "Bio::Cells", "count": 4}
