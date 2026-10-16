# ADR-001: Tauri 2 shell, React UI, Python engine

- Status: accepted (2026-10-15)
- Roadmap: A03

## Context

SFCM for Anki must run on Windows, macOS and Linux and do three jobs: generate styled cards from a form, turn folders of documents into cards, and improve existing decks. It has to read and write Anki's package formats faithfully, parse many document types, and call AI providers.

## Decision

Three parts, each with one job:

| Part | Language | Owns |
|---|---|---|
| Shell (`app/src-tauri`, `app/engine-host`) | Rust, Tauri 2 | Windows, file dialogs, OS keychain, auto-update, starting and supervising the engine |
| UI (`ui/`) | TypeScript, React | Everything on screen |
| Engine (`engine/`) | Python 3.12 | Anki I/O with the official `anki` package, document parsing, AI provider calls, jobs, the app database |

The UI talks to the engine through the shell: JSON-RPC 2.0 over the engine's stdin/stdout, newline-delimited, in the style of LSP (`$/progress`, `$/cancelRequest`). The shell routes messages without interpreting them. The engine can ask the shell for things, currently only `secrets/get`.

Rules that keep the boundaries clean:

- The shell never parses documents or calls AI providers.
- The engine never touches the UI or the keychain directly.
- API keys go from the UI to the keychain through the shell, and reach the engine only when it asks for one for a specific call.
- The protocol is declared once, in `engine/src/sfcm_engine/protocol.py`. `just gen` exports a JSON Schema and generates TypeScript types from it; CI fails if they drift.

## Why Python for the engine

- The official `anki` package (Anki's Rust core with Python bindings) reads and writes every Anki format Anki itself supports, including the newer zstd-compressed collection format and Image Occlusion notes. Reimplementing that is a large ongoing cost.
- Python has the strongest document-parsing ecosystem (PDF, DOCX, OCR).
- Official SDKs exist for Anthropic and OpenAI.

The cost is packaging: the engine is frozen with PyInstaller (`--onedir`) and shipped as an app resource, about 40 MB today. Provider SDKs are imported on first use so the engine reports ready in under a second.

## Licensing consequence

Linking the `anki` package (AGPL-3.0) makes the whole app AGPL-3.0-or-later (roadmap A02). Dependencies must be AGPL-compatible; CI checks this.

## Alternatives considered

- **Electron instead of Tauri:** larger installers (Chromium bundled) and higher memory use, with no capability we need that Tauri lacks.
- **PySide6 only (no web UI):** one language, but a dated UI toolkit and weaker tooling for the rich card previews the app depends on.
- **No Python (Rust + TypeScript, own `.apkg` reader/writer):** smaller and allows a permissive license, but means reimplementing and tracking Anki's file formats, and weaker PDF parsing. Rejected for now; revisit if packaging Python becomes a problem.

## Process lifecycle

- Debug builds run the engine from source with `uv run`; release builds run the bundled executable. `SFCM_ENGINE_CMD` overrides both for debugging.
- The engine writes `$/ready` with its protocol version. A mismatch is fatal (no restart) and the UI tells the user to reinstall.
- If the engine exits, in-flight requests fail and the shell restarts it with backoff (1, 2, 4, 8, 16, then 30 s). After 5 quick failures it gives up and shows the reason.
- The engine exits when its stdin closes, so it cannot outlive the app even if the app is killed. On normal exit the shell closes stdin, waits 3 s, then kills it.
