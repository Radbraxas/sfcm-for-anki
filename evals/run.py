# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run the card-quality eval (roadmap A11).

    just eval                       # all sources, default models
    just eval --count 6 --fail-on-regression
    just eval --update-baseline     # after a deliberate prompt or model change

Needs ANTHROPIC_API_KEY (or OPENAI_API_KEY with --provider openai). Every run spends
real money: roughly (sources x count) generated cards plus one judge call per source.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from evals.metrics import (
    SourceResult,
    aggregate,
    count_duplicates,
    count_lint_clean,
    mean,
    regressions,
    render_markdown,
    to_json,
)
from sfcm_engine.db import Database
from sfcm_engine.generation import generate_cards
from sfcm_engine.llm.base import StructuredRequest
from sfcm_engine.llm.registry import JUDGE_MODEL, ProviderRegistry
from sfcm_engine.prompts import PromptLibrary
from sfcm_engine.protocol import CardsGenerateParams, ProviderId
from sfcm_engine.secrets import EnvKeySource

HERE = Path(__file__).resolve().parent


class CardScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    faithfulness: int
    atomicity: int
    clarity: int
    note: str


class JudgeReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: list[CardScore]


def clamp(score: int) -> float:
    return float(min(5, max(1, score)))


async def eval_source(
    path: Path,
    args: argparse.Namespace,
    registry: ProviderRegistry,
    prompts: PromptLibrary,
) -> tuple[SourceResult, str, str]:
    provider_id: ProviderId = args.provider
    provider = registry.resolve(provider_id)
    key = await EnvKeySource().get(provider_id)
    model = args.model or registry.model_for(provider_id)
    text = path.read_text(encoding="utf-8")
    outcome = await generate_cards(
        CardsGenerateParams(source=text, source_label=path.name, count=args.count),
        provider=provider,
        model=model,
        api_key=key,
        prompts=prompts,
    )
    cards = outcome.cards

    judge_prompt = prompts.render(
        "eval_judge",
        source_label=path.name,
        source=text,
        cards_json=json.dumps(
            [
                {
                    "index": i,
                    **c.model_dump(include={"note_type", "front", "back", "text", "why"}),
                }
                for i, c in enumerate(cards)
            ],
            indent=1,
        ),
    )
    judge = await provider.generate(
        StructuredRequest(
            system=judge_prompt.system,
            user=judge_prompt.user,
            model=args.judge_model,
            effort="low",
        ),
        JudgeReply,
        key,
    )
    scores = judge.value.scores
    result = SourceResult(
        source=path.name,
        accepted=len(cards),
        rejected=outcome.rejected,
        lint_clean=count_lint_clean(cards),
        duplicates=count_duplicates(cards),
        judge={
            "faithfulness": mean([clamp(s.faithfulness) for s in scores]),
            "atomicity": mean([clamp(s.atomicity) for s in scores]),
            "clarity": mean([clamp(s.clarity) for s in scores]),
        },
        cost_usd=outcome.usage.cost_usd,
        notes=[f"#{s.index}: {s.note}" for s in scores if s.note],
    )
    return result, outcome.prompt_version, outcome.model


async def main_async(args: argparse.Namespace) -> int:
    db = Database(":memory:")
    db.migrate()
    registry = ProviderRegistry(db)
    prompts = PromptLibrary()
    sources = sorted(Path(args.sources).glob("*.md"))
    if not sources:
        print(f"no sources in {args.sources}", file=sys.stderr)
        return 2

    results: list[SourceResult] = []
    prompt_version = model = ""
    for path in sources:
        print(f"... {path.name}", file=sys.stderr)
        result, prompt_version, model = await eval_source(path, args, registry, prompts)
        results.append(result)

    summary = aggregate(results)
    baseline_path = Path(args.baseline)
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else None
    regressed = regressions(baseline, summary) if baseline else []
    meta = {
        "model": model,
        "prompt_version": prompt_version,
        "judge_model": args.judge_model,
        "count": args.count,
    }
    report = render_markdown(summary, results, meta, baseline, regressed)

    out = Path(args.out) / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report, encoding="utf-8")
    (out / "report.json").write_text(
        json.dumps({"meta": meta, "summary": summary, "sources": to_json(results)}, indent=2),
        encoding="utf-8",
    )
    print(report)
    print(f"Report written to {out}", file=sys.stderr)

    if args.update_baseline:
        baseline_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Baseline updated: {baseline_path}", file=sys.stderr)
    return 1 if (regressed and args.fail_on_regression) else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="just eval")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--model", default=None, help="generator model (default: provider default)")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--count", type=int, default=10, help="cards per source")
    parser.add_argument("--sources", default=str(HERE / "datasets" / "sources"))
    parser.add_argument("--out", default=str(HERE / "reports"))
    parser.add_argument("--baseline", default=str(HERE / "baseline.json"))
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
