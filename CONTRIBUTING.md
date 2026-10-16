# Contributing to SFCM for Anki

Thanks for helping. This guide covers how to get set up, how changes are reviewed, and the few rules every change follows.

## Getting set up

Follow [docs/dev-setup.md](docs/dev-setup.md). `just setup && just dev` should open the app within 15 minutes on a fresh machine. If it doesn't, that is a bug: please open an issue.

## Finding something to work on

- Tasks come from [docs/roadmap.csv](docs/roadmap.csv) and are mirrored as GitHub issues with the same IDs (A01, C04, ...).
- Issues labelled `good first issue` are small and well described.
- For anything larger than a bug fix, comment on the issue first so we can agree on the approach.

## Making a change

1. Branch from `main`.
2. Keep each pull request to one task. Small PRs get reviewed faster.
3. Run `just lint` and `just test` before pushing. CI runs the same checks on Windows, macOS (Apple Silicon and Intel) and Linux.
4. If you change `engine/src/sfcm_engine/protocol.py`, run `just gen` and commit the generated files.
5. If you change a prompt, copy it to a new version folder instead of editing a released one, note it in `prompts/CHANGELOG.md`, and include `just eval` results in the PR if you can.

## Commit messages

- Use [Conventional Commits](https://www.conventionalcommits.org): `feat(engine): parse docx tables`, `fix(ui): keep focus after save`. Allowed types: build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test. Release notes and version numbers are generated from these.
- Sign off every commit (`git commit -s`). This adds a `Signed-off-by:` line certifying the [Developer Certificate of Origin](https://developercertificate.org): that you wrote the change or have the right to submit it under the project license. We use the DCO instead of a contributor license agreement.

The `commit-msg` git hook installed by `just setup` checks both rules locally.

## Code rules

- Every source file starts with an `SPDX-License-Identifier: AGPL-3.0-or-later` comment.
- New dependencies must have an AGPL-compatible license ([docs/licenses.md](docs/licenses.md)). CI checks this.
- Never paste code from projects with incompatible licenses.
- Never log or print API keys or card content at INFO level or above.
- The engine returns error *reasons* (`missing_api_key`), never user-facing text. The UI turns reasons into words.

## Reporting bugs and card-quality problems

Use the issue forms. For bad cards, the "Card quality" form asks for the source text, the settings and the cards you got. That is the fastest way to improve the prompts.

Security problems go through private reporting; see [SECURITY.md](SECURITY.md).

## Code of conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).
