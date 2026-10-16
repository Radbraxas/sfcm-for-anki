-- SPDX-License-Identifier: AGPL-3.0-or-later
-- One row per model call, for cost reporting (A09) and the eval harness (A11).
CREATE TABLE generation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    cards_accepted INTEGER NOT NULL DEFAULT 0,
    cards_rejected INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX generation_log_created_at ON generation_log (created_at);
