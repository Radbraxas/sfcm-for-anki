-- SPDX-License-Identifier: AGPL-3.0-or-later
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,             -- JSON
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
