# AI4Finance Integration Sandbox Plan

## Purpose

This document defines an isolated AI4Finance-inspired production-integration sandbox for NCN.
The sandbox is for evaluating evidence, review, replay, risk, and audit patterns inside `experiments/ai4finance/` before any separate promotion decision.

NCN is moving toward production-stage human review and paper/simulation workflows, but this sandbox must not reuse normal entrypoints, production YAML, or main-flow tests. The only allowed external project inputs are stock data and `Key/ts.key`.

## Hard Boundaries

The sandbox must not modify, call, or depend on these protected production paths:

- `main.sh`
- `mkf.sh`
- `scripts/edge_scout_scan.sh`
- `yaml/mkf_ai_review.yaml`
- `yaml/news_ai_review.yaml`
- `output/edge_scout/latest.json`

The sandbox may read only these external project inputs:

- `PFrontStockData/`
- `Key/ts.key`

The sandbox must not add:

- live broker login
- live order submission
- leverage
- custody or settlement behavior
- unattended real-money execution
- BUY/HOLD/AVOID output in the production MKF prompt
- portfolio weights that flow to live execution
- target price, position sizing, stop-loss, take-profit, or return promises

All experiment output must stay under ignored runtime paths such as:

- `.runtime/ai4finance/`

## Reference Value From AI4Finance

AI4Finance is useful as a reference ecosystem, not as a direct dependency to copy wholesale.

| Source | Useful reference | NCN sandbox use |
|---|---|---|
| FinNLP | financial news and sentiment data pipelines | evaluate better news/evidence context design |
| FinGPT | financial LLM benchmarks and sentiment tasks | define output-quality and grounding rubrics |
| FinRobot | role-based financial research agents and committee-style workflows | evaluate staged review and traceable committee reports |
| FinRAG | retrieval-augmented financial evidence | design future evidence packs and provenance |
| FinRL / FinRL-Trading | modular strategy/backtest/risk architecture | inform paper/simulation and promotion gates only |

## Sandbox Architecture

The intended isolated architecture is:

```text
sandbox-local candidate or replay input
  -> frozen candidate evidence pack
  -> experimental prompt replay
  -> output-quality evaluator
  -> optional target-timeout outcome join when mature
  -> promotion gate report
```

No stage writes to production scan outputs or changes default MKF behavior.

## Directory Layout

```text
experiments/ai4finance/
├── amkf.sh
├── README.md
├── configs/
│   └── ai4finance_mkf_experiment.yaml
├── prompts/
│   └── README.md
├── reports/
│   └── README.md
└── yaml/
    ├── ai_providers.yaml
    ├── mkf_ai_review_sandbox.yaml
    └── mkf_news_context_sandbox.yaml

.runtime/ai4finance/
├── evidence-packs/
├── replay-runs/
├── comparisons/
├── eval-reports/
└── logs/
```

Only the `experiments/ai4finance/` source files are tracked. Runtime outputs remain untracked.

## Initial Experiment Scope

The first sandbox iteration may create tools for:

1. building read-only candidate evidence packs from sandbox-local inputs and `PFrontStockData/`;
2. replaying sandbox-local prompts through sandbox-local configs;
3. evaluating review outputs for schema, evidence grounding, risk specificity, and action-label avoidance;
4. comparing experimental outputs against sandbox-local baselines;
5. later joining mature outcomes using the established target-timeout method.

## Evaluation Rubric

A candidate prompt or workflow can only be considered for later promotion if it improves or preserves these dimensions:

- persisted schema validity;
- AI available/scored count;
- forbidden response-key count;
- operation/action-label avoidance;
- use of real OHLCV/candlestick/news evidence;
- no fabricated policy, announcement, financial, legal, sector, or fund-flow facts;
- risk-specificity and risk-attention usefulness;
- cross-candidate readability for short-swing human review;
- replay reproducibility through config SHA, prompt SHA, model, provider, and input evidence hashes;
- later target-timeout outcome relationship after enough future bars exist.

## Promotion Gate

Promotion out of the sandbox requires a separate explicit decision and a separate implementation change.

Minimum gate before discussing promotion:

1. Protected production entrypoints and YAML remain unchanged.
2. The experiment has a sandbox-local baseline and does not require production YAML at runtime.
3. Experimental output schema success is not worse than the sandbox-local baseline.
4. Forbidden fields and action-label risks are not worse than the sandbox-local baseline.
5. AI unavailable count is not worse than the sandbox-local baseline.
6. Multi-day replay supports the change, not only one 23-candidate sample.
7. If outcome data is used, it follows the established target-timeout method: T+1..T+N future high, buy-day high excluded, T+20 close fallback for misses.
8. The change does not add live trading, broker, order, leverage, or real-money behavior.

## Current Recommendation

Keep production prompt behavior outside this sandbox unless a separate promotion decision is made.
Use this sandbox to test AI4Finance-inspired evidence, replay, evaluation, and risk-review structure without changing production commands.
