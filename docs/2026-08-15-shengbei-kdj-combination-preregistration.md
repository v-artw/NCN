# Shengbei State Plus KDJ Trigger Preregistration

## Objective

Test exactly one previously proposed state-plus-trigger hypothesis over the
already frozen current-main-board universe: a KDJ Trend Pro buy trigger while
Shengbei was already in its long state. This is a five-tradable-day
classification study, not a return, execution, or profit backtest.

## Frozen Signal And Comparators

- The combination is true at T only when `shengbei_state` was exactly `1` at
  T-1 and the existing `kdj_trend_pro_buy` trigger is true at T.
- Requiring the T-1 state prevents a same-bar Shengbei flip from being counted
  as independent confirmation. No minimum state age, stop distance, oscillator
  threshold, or alternative pair is permitted.
- Formula values, tradable-row handling, production admission gates, label,
  periods, current-main-board prefixes, and per-stock five-index spacing remain
  exactly as frozen in the two Futu ranking preregistrations.
- The market comparator is the existing signal-count-weighted same-date mature
  admitted baseline on dates with at least 150 mature admitted stocks.
- The parent comparator is every mature admitted KDJ Trend Pro trigger on the
  combination's signal dates. Its date precision is weighted by the
  combination's signal count so combination and parent have identical date
  weights. Primary parent observations use the same per-stock five-index
  spacing; all-origin comparison is also reported.

## Frozen Gates And Decision

The combination must pass all existing standalone selection gates in
2023-2024: primary n at least 300, at least 120 dates, at least 50 codes, annual
n at least 50, positive annual market-baseline lift, aggregate market-baseline
lift at least 3 points, Wilson lower bound above the market baseline, and
positive all-origin market-baseline lift.

It must also exceed its matched parent KDJ precision by at least 1 point in the
2023-2024 primary aggregate. Audit acceptance in 2025-2026 independently
requires the existing audit gates and at least 1 point over matched parent KDJ.
The parent comparison is an aggregate gate; annual parent deltas are reported
but are not extra gates. Passing retrospective gates would authorize only
unchanged prospective observation, not scanner promotion.

## Fixed Data And Budget

- Universe: all sorted current main-board files with prefixes `sh.600`,
  `sh.601`, `sh.603`, `sh.605`, `sz.000`, `sz.001`, `sz.002`, or `sz.003`.
- Expected frozen code-list SHA-256:
  `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`.
  Abort rather than evaluate if the list differs.
- Environment order is WSL, Doris, then local. Use at most 8 workers and one
  BLAS thread per worker after checking memory pressure.
- One full-universe outcome run. Persist detached PID, log, exit status, atomic
  result, and result SHA-256. Do not run a 400-code screen first.
- Stop and reject the combination on any failed frozen gate. Do not inspect
  other pairs/triples or alter the signal after observing the result.
