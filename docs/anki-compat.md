# Anki compatibility

SFCM for Anki reads and writes decks with Anki's own Python package (`anki` on PyPI), pinned to one release in `engine/pyproject.toml` (roadmap A15).

## Current pin

| Package | Version | Pinned on |
|---|---|---|
| `anki` | 26.9.3 | 2026-10-16 |

## Package formats we write

| Export option | Inner file | Imports into |
|---|---|---|
| Modern (default) | `collection.anki21b` (zstd-compressed) | Anki desktop 2.1.50 and later |
| Legacy (`legacy=True`) | `collection.anki21` | Older Anki desktop versions too; use this when users on old mobile apps report import failures |

Minimum AnkiDroid and AnkiMobile versions are not yet confirmed. They are checked by hand with the release checklist (roadmap B10); record results here.

| Client | Modern format | Legacy format | Checked |
|---|---|---|---|
| Anki desktop 26.09 | expected yes | expected yes | automated (engine tests) |
| AnkiDroid | not yet checked | not yet checked | |
| AnkiMobile | not yet checked | not yet checked | |

## Bumping the pin

The `anki-compat` workflow runs every Monday. It installs the newest `anki` release, runs the engine tests (including `test_anki_compat.py`, which exports and re-imports a deck in both formats), and opens an issue if anything fails.

To bump:

1. `uv add --project engine "anki==<new version>"` and keep the `==` pin.
2. `just test` and `just build-engine` (the frozen engine must still start).
3. Import an exported deck into Anki desktop and at least one mobile app.
4. Update the tables above in the same commit.
