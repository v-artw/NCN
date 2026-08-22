# Prospective Watchlist Archive Contract

## Objective

Create an untouched, forward-collected record of NCN's daily read-only research
watchlist and evaluate it only after the fixed five-tradable-close outcome has
matured. This archive measures selection quality and false positives. It does
not calculate returns, simulate execution, manage a portfolio, or authorize
trading.

## Eligible Snapshots

- Every successful market scan publishes `prospective_snapshot.json` inside its
  existing immutable run directory.
- Only scans using automatic `as_of` selection are prospective-eligible. Manual
  `--as-of` scans are archived for audit but excluded from prospective metrics.
- A snapshot records its publication time, signal date, latest data date visible
  to the scan, run ID, configuration SHA-256, source artifact hashes, baseline
  rows, selected rows, reasons, scores, and structured risk codes.
- For a repeated signal date, the earliest valid publication is canonical.
  Later snapshots are reported as duplicates and cannot replace it.
- A snapshot is not eligible if its publication timestamp predates its visible
  data date, its manifest/hash contract fails, or required fields are invalid.

The automatic scanner currently uses signal T = latest visible market date
minus two trading dates. Therefore T+1 and T+2 may already be visible when the
watchlist is published. The archive reports this explicitly and must never call
the evidence a pristine T-origin forecast.

## Frozen Cohorts

- `all_watch`: every row in `daily_research_watchlist.csv`.
- `confirmed_watch`, `setup_watch`, `cnstock_pool_watch`, and
  `discovery_watch`: the existing mutually exclusive watch stages.
- `admitted_baseline`: every scored stock in the same scan, whether watchlist or
  near miss. It is not a selected cohort.

No stage definition, rank cutoff, score threshold, or retrospective subgroup
may be changed after outcomes. Metrics are reported for all stages, but
`all_watch` versus the same-date admitted baseline is the primary operational
comparison.

## Frozen Outcome

- Reference is the archived T close (`research_close`).
- Read current local bars only when auditing, never when creating the snapshot.
- Starting after T, skip rows with `tradestatus != 1` and collect exactly five
  tradable closes.
- Hit if at least one close reaches T close +3% and no close is below T close
  -3%; otherwise false positive.
- Maturity date is the fifth future tradable row.
- If fewer than five future tradable rows exist, status is `pending`.
- If current T close differs from the archived close beyond absolute tolerance
  `1e-6` and relative tolerance `1e-8`, status is `data_revision`; it is excluded
  from outcomes rather than silently relabeled.
- Missing files, dates, invalid bars, and hash failures are reported separately
  and excluded.

## Reporting

- Preserve each audit as a new immutable JSON file; never overwrite an earlier
  audit.
- Report snapshot counts, canonical/duplicate/ineligible runs, pending/mature/
  revised/missing observations, n, hits, false positives, precision, Wilson 95%
  interval, dates, codes, watch-stage metrics, same-date admitted baseline, and
  precision lift.
- Do not claim effectiveness before at least 300 mature `all_watch`
  observations, at least 120 canonical signal dates, at least 50 codes, and an
  `all_watch` Wilson lower bound above its matched baseline. These are evidence
  sufficiency gates, not a promise of scanner promotion.
- Annual and regime stability remain required before any later behavior change.

## Operational Boundary

- Snapshot publication is part of the existing atomic scan publication.
- Audit failures must not mutate snapshots or scanner outputs.
- The scanner, ranking logic, watch stages, Web behavior, YAML, and
  `production_enabled: false` remain unchanged.
- No historical run lacking `prospective_snapshot.json` may be reconstructed and
  presented as prospective evidence.
