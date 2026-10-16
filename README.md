# SFCM for Anki

An open-source desktop app (Windows, macOS, Linux) that makes and improves Anki flashcards with AI:

1. **Card Studio:** fill in a form and get well-formed, nicely styled cards that use every Anki note type.
2. **Folder to cards:** point it at a folder of notes (Markdown, text, Word, PDF and more) and get cards, kept in sync as the notes change.
3. **Deck improver:** load a deck you already have and get reviewed, rewritten and completed cards, without losing your review history.

> Status: early development. The foundations (app shell, engine, AI providers, CI) are in place; the three features are on the [roadmap](docs/roadmap.csv).

SFCM for Anki is not affiliated with or endorsed by Anki or Ankitects.

## How it works

A Rust (Tauri 2) shell runs a React interface and a Python engine. The engine uses Anki's own library to read and write decks, and calls the AI provider you choose: Anthropic Claude, OpenAI, or a local model through Ollama or LM Studio. With **local only** turned on, nothing leaves your computer.

API keys are stored in your operating system's keychain, never in files. See [ADR-001](docs/adr/0001-architecture.md) for the architecture.

## Developing

See [docs/dev-setup.md](docs/dev-setup.md). In short:

```bash
just setup
just dev
```

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## License

[AGPL-3.0-or-later](LICENSE). See [docs/licenses.md](docs/licenses.md) for why, and for the dependency policy.
