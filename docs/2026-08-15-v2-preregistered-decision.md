# Edge Scout V2 Pre-registered Decision

## Actionable Hypothesis

For the existing four bullish reversal candle families, requiring a local
pullback plus a touch-and-reclaim of an independent support level, followed by
pattern-specific T+1 confirmation, will reduce five-bar false positives versus
the current T-day setup.

This tests Nison's context, location, confirmation, and failure principles. It
does not test extra oscillator combinations or historical returns.

## Fixed Candidate Set

- `legacy_setup`: current trend, pullback, and enabled-pattern setup.
- `support_reclaim_t`: legacy major-trend context plus a pre-T local decline,
  one support touch/reclaim, and one existing bullish pattern on T.
- `support_reclaim_confirmed`: `support_reclaim_t` plus pattern-specific T+1
  confirmation and no explicit pattern failure.

No additional filters, thresholds, or candidate families may be added after
results are observed.

## Fixed Label And Periods

- Label: within T+1 through T+5, at least one close reaches T close +3%, and no
  close falls below T close -3%.
- Leakage correction fixed before observing results: because T+1 is consumed by
  confirmation, confirmed candidates and the legacy comparison use T+2 through
  T+6 relative to T+1 close. T-day-only diagnostics retain the original
  T+1-through-T+5 label. The acceptance decision compares only equal horizons.
- Calibration/decision evidence: 2021-2024.
- Untouched acceptance period: 2025-2026.
- Current-file main-board universe and adjusted-data limitations remain
  explicit; this is selected-stock classification, not a return backtest.

## Success Thresholds

The v2 direction passes only when `support_reclaim_confirmed` satisfies all of:

- At least 20% relative false-positive-rate reduction versus `legacy_setup`.
- At least 40% of `legacy_setup` candidate count retained.
- At least 300 matured observations in both 2021-2024 and 2025-2026.
- Positive precision lift in both periods.
- The 95% Wilson lower bound does not deteriorate versus `legacy_setup` in
  either period.

The T-day-only support filter is diagnostic and cannot pass the direction by
itself.

## Compute Budget And Stop Rule

- Stage 1: deterministic 400-code sample, every eligible date from 2021.
- Stage 2: all current main-board files only if Stage 1 passes every threshold.
- Maximum one run per stage. No post-hoc threshold changes.
- Failure at Stage 1 rejects this direction. Failure at Stage 2 prevents runtime
  integration. In either case, do not mine the same period for replacement
  filters.

## Implementation Decision

- Pass Stage 2: introduce an `edge_scout_v2` staged decision contract and route
  the selected watchlist only through context, support, trigger, confirmation,
  and explicit risk decisions.
- Fail: retain the tagged V1 runtime, keep the v2 code research-only, and move
  to a separately pre-registered continuation-pattern hypothesis rather than
  modifying this one.
