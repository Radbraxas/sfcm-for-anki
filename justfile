# SFCM for Anki - task runner. Run `just` to list recipes.

set windows-shell := ["pwsh", "-NoLogo", "-NoProfile", "-Command"]

engine := "uv run --project engine"

# List recipes
default:
    @just --list

# Install all dependencies and git hooks
setup:
    uv sync --project engine
    pnpm install
    pnpm exec lefthook install

# Run the desktop app with a live engine and hot-reloading UI
dev:
    pnpm tauri dev

# Run the engine alone on stdio (for debugging the protocol)
engine:
    {{engine}} python -m sfcm_engine

# --- Tests -----------------------------------------------------------------

test: test-engine test-ui test-app

test-engine:
    {{engine}} pytest -c engine/pyproject.toml engine/tests evals/tests

test-ui:
    pnpm --filter @sfcm/ui test

# Tauri embeds ui/dist at compile time, so build it before compiling the app crate.
test-app: ui-dist
    cargo test --workspace

# --- Lint ------------------------------------------------------------------

lint: lint-engine lint-ui lint-app

lint-engine:
    {{engine}} ruff check engine evals scripts app
    {{engine}} ruff format --check engine evals scripts app
    {{engine}} pyright -p engine

lint-ui:
    pnpm exec biome check .
    pnpm --filter @sfcm/ui typecheck

lint-app: ui-dist
    cargo fmt --all --check
    cargo clippy --workspace --all-targets -- -D warnings

# Format everything in place
fmt:
    {{engine}} ruff format engine evals scripts
    {{engine}} ruff check --fix engine evals scripts
    pnpm exec biome check --write .
    cargo fmt --all

ui-dist:
    pnpm --filter @sfcm/ui build

# --- Generated code --------------------------------------------------------

# Regenerate the protocol JSON Schema and the TypeScript types
gen:
    {{engine}} python engine/scripts/export_schema.py engine/schema/protocol.schema.json
    pnpm --filter @sfcm/ui gen:types

# Fail if generated files are out of date (used in CI)
check-gen: gen
    git diff --exit-code -- engine/schema ui/src/ipc/protocol.gen.ts

# --- Licenses --------------------------------------------------------------

licenses:
    {{engine}} python scripts/check_licenses.py

# --- Build -----------------------------------------------------------------

# Freeze the Python engine into engine/dist/sfcm-engine (onedir)
build-engine:
    {{engine}} pyinstaller engine/sfcm-engine.spec --distpath engine/dist --workpath engine/build --noconfirm

# Build installers for the current OS
build: build-engine
    pnpm tauri build --config app/src-tauri/tauri.bundle.json

# --- Live provider check ---------------------------------------------------

# Send one small real request to each reachable provider (costs a few cents with keys)
smoke *PROVIDERS:
    {{engine}} python engine/scripts/live_smoke.py {{PROVIDERS}}

# Render every card theme in light and night mode to .sfcm-data/theme-preview.html
theme-preview:
    {{engine}} python engine/scripts/theme_preview.py .sfcm-data/theme-preview.html

# Export the sample deck in every theme (default: .sfcm-data/samples)
sample-deck *DIR:
    {{engine}} python engine/scripts/sample_deck.py {{DIR}}

# --- Evals -----------------------------------------------------------------

# Score card quality against the golden sources (needs ANTHROPIC_API_KEY)
eval *ARGS:
    {{engine}} python -m evals.run {{ARGS}}
