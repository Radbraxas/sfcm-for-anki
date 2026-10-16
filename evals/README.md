# Card quality evals

`just eval` generates cards from each file in `datasets/sources/`, scores them, and compares the result with `baseline.json`.

## What is measured

| Metric | How | Better |
|---|---|---|
| `schema_validity` | accepted cards / all cards the model returned | higher |
| `lint_pass_rate` | accepted cards with no rule warnings (`sfcm_engine.quality.lint`) | higher |
| `duplicate_rate` | near-copies (word-set Jaccard >= 0.8) / accepted cards | lower |
| `faithfulness`, `atomicity`, `clarity` | 1-5 per card from an LLM judge (`prompts/eval_judge`) | higher |
| `cost_per_accepted_card_usd` | generation cost / accepted cards (judge cost excluded) | lower |

A drop of more than 5% in any tracked metric is reported as a regression. With `--fail-on-regression` the command exits non-zero, which is how CI uses it.

## Running

```bash
export ANTHROPIC_API_KEY=...
just eval --count 8
```

Each run costs money: one generation call per source plus one judge call per source. With the three bundled sources and default models, expect a few cents.

After a deliberate change (new prompt version, new default model), review the report, then record it as the new baseline:

```bash
just eval --update-baseline
```

No baseline is committed yet. The first maintainer run with an API key creates it.

## Sources

The bundled sources are short original texts written for this project (biology, networking, language learning) so the eval covers different card styles. Add longer, openly licensed material such as OpenStax textbook sections (CC BY 4.0) with attribution in the file header.

Reports are written to `evals/reports/<timestamp>/` and are not committed.
