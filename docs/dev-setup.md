# Development setup

You need Rust (stable), [uv](https://docs.astral.sh/uv/), Node 22 with pnpm 9 (via `corepack enable`), and [just](https://just.systems). Then, per OS:

## Linux (Debian/Ubuntu)

```bash
sudo apt-get install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev libssl-dev libdbus-1-dev pkg-config build-essential patchelf file
```

Fedora and Arch package names are in the [Tauri prerequisites guide](https://v2.tauri.app/start/prerequisites/). A Secret Service provider (GNOME Keyring or KWallet) must be running for API keys to be saved.

## macOS

```bash
xcode-select --install
```

## Windows

Install the "Desktop development with C++" workload from Visual Studio Build Tools. WebView2 ships with Windows 10 (1803+) and 11.

## First run

```bash
just setup   # Python and JS dependencies, git hooks
just dev     # opens the app; the engine runs from source
```

`just` lists every recipe. The ones you will use most:

| Recipe | Does |
|---|---|
| `just test` | engine (pytest), UI (vitest) and Rust tests |
| `just lint` | ruff, pyright, Biome, tsc, rustfmt, clippy |
| `just fmt` | formats everything |
| `just gen` | regenerates protocol schema and TS types after editing `protocol.py` |
| `just engine` | runs the engine alone on stdio, for poking at the protocol |
| `just build` | freezes the engine and builds installers for your OS |
| `just eval` | card-quality eval; needs `ANTHROPIC_API_KEY` and costs money |

## Talking to the engine by hand

```bash
just engine
{"jsonrpc":"2.0","id":1,"method":"engine/info","params":{}}
```

Each line you type is one request; each line printed is one response or notification. Logs go to stderr. The database lives in `.sfcm-data/` when run this way.
