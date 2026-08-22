# SMC + News Prospective Evidence Contract

Date: 2026-08-20

## Scope

This contract governs the read-only SMC selection plus news/K-line AI review evidence chain. It is an evidence-collection and audit contract only. It does not create trading, order, fill, portfolio, return, P&L, or personalized buy/sell semantics.

## Artifact Chain

A valid SMC+News prospective observation must be bound through this immutable chain:

1. `output/edge_scout/selections/select-*` — automatic-date SMC selection with `prospective_eligible=true`.
2. `output/edge_scout/news_reviews/news-review-*` — news/K-line AI review bound to the selection `candidates.json` SHA-256.
3. `output/edge_scout/smc_news_prospective/smc-news-*` — prospective archive binding the exact selection and news-review manifests.
4. `output/edge_scout/smc_news_prospective_audits/smc-news-audit-*.json` — maturity audit against later adjusted research bars.

Manual `--as-of` selection or review runs are permanently excluded from SMC+News prospective evidence. They may be useful for inspection, but they must not be archived as prospective proof.

## Review Semantics

News/K-line AI states are human-review buckets only:

- `priority_review`
- `standard_review`
- `risk_excluded`
- `insufficient_evidence`
- `ai_unavailable`

These states are not validated probabilities, returns, recommendations, orders, or execution signals. Favorable AI cannot bypass SMC selection, and AI/news/model failures fail closed.

`review-news --top N` is display-only. It limits terminal output rows but does not limit processing or the immutable JSON/CSV artifact content.

## Replay Boundary

`replay-smc-news` is simulation-only artifact audit. Replay outputs are not point-in-time evidence and must never be used as prospective evidence or as a basis to change SMC admission, ranking, thresholds, or risk exclusions.

## Promotion Gates

`priority_review` must not be promoted to selection logic unless a future unchanged prospective audit passes all fixed gates:

- at least 300 mature reviewed priority observations,
- at least 120 publication dates,
- at least 50 distinct codes,
- at least 20% retention versus parent SMC candidates,
- at least +3 percentage points target-touch precision versus same-date parent SMC,
- priority Wilson lower 95% above the same-date parent SMC precision,
- positive annual lifts.

Until those gates pass, `precision_improvement_claimed` remains `false`, and the project must not claim that News AI improves win rate.

## Audit Fields

SMC+News audits should distinguish:

- parent SMC maturity sufficiency, and
- News AI promotion sufficiency.

A mature parent SMC cohort alone is not evidence that News AI improves selection quality.
