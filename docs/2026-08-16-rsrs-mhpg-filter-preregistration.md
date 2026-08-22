# RSRS Structure-Quality Filter Preregistration

## Objective

Test whether one deterministic RSRS structure-quality filter reduces false
positives among existing `mhpg_buy` candidates. This is a five-tradable-close
classification study, not a return, execution, portfolio, or profitability
study.

This document freezes the signal, sample, comparisons, gates, budget, and stop
rule before outcome computation.

## Fixed Hypothesis

The parent signal is the already frozen `mhpg_buy` trigger:

- EMA20 above EMA60 and EMA60 rising versus T-1.
- A bullish cross of 30-day KD(3,3).
- K strictly below 60.

The only candidate is `mhpg_rsrs_quality`:

- `mhpg_buy` is true at T.
- On tradable stock rows, regress the latest 18 highs on the corresponding 18
  lows with an intercept.
- The rolling slope is `(covariance(low, high) / variance(low))`.
- `R2` is the squared Pearson correlation of low and high in that window.
- Standardize the slope at T against the latest 600 available rolling slopes,
  including T, using sample standard deviation (`ddof=1`).
- Require `RSRS_Z > 0.7` and `R2 >= 0.8` at T.

The 18/600 windows and `RSRS_Z > 0.7` come from the reviewed stockAI RSRS
implementation and scanner threshold. The `R2 >= 0.8` structure-quality floor
is a project-defined fixed mapping. Invalid windows, non-positive low variance,
or zero slope standard deviation are unavailable and cannot pass. Suspensions
do not enter the RSRS or MHPG timeline.

No XGBoost, HMM, probability output, ATR/RSI/bias/volume model feature, formula
mining, or alternate RSRS definition is allowed.

## Fixed Data And Label

- All sorted current main-board Parquet files whose code begins with `sh.600`,
  `sh.601`, `sh.603`, `sh.605`, `sz.000`, `sz.001`, or `sz.002`.
- The code-list SHA-256 must equal the previously audited full-universe hash
  `42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e`.
- Every eligible tradable origin from 2021-01-01 through local-data end.
- Calibration 2021-2022 is reporting only.
- Selection period: 2023-2024.
- Retrospective audit period: 2025-2026; it is not a pristine holdout.
- Existing production-aligned code, ST, listing-age, price, ADV20,
  recent-trading, suspension, and near-limit-up gates apply at T.
- Hit: among the next five tradable closes, at least one reaches +3% from T
  close and none closes below -3% from T close.

## Comparisons And Primary Observations

- Per-stock candidate origins spaced at least five tradable rows apart are the
  primary observations. All origins are reported as sensitivity.
- Market comparison uses the existing candidate-count-weighted same-date mature
  admitted baseline. A date is usable only with at least 150 admitted stocks.
- The decisive parent comparison is MHPG triggers on candidate signal dates,
  weighted by candidate count. Primary parent MHPG origins are independently
  spaced at least five tradable rows apart; all parent origins are used in the
  sensitivity report.
- Report n, hits, false positives, precision, Wilson 95% interval, signal dates,
  codes, same-date market precision/lift, matched-parent precision/lift, annual
  metrics, all-origin sensitivity, and RSRS availability/trigger coverage.

## Frozen Gates

Selection eligibility requires all of the following in 2023-2024:

- At least 300 primary observations, 120 signal dates, 50 codes, and at least
  50 observations in each year.
- Positive market-baseline lift in both years, aggregate market lift at least 3
  percentage points, candidate Wilson lower bound above aggregate market
  baseline, and positive all-origin market lift.
- Positive matched-parent MHPG lift in both years, aggregate matched-parent lift
  at least 3 percentage points, candidate Wilson lower bound above aggregate
  matched-parent precision, and positive all-origin matched-parent lift.

Audit acceptance requires the corresponding 2025-2026 gates, with at least 50
observations in 2025 and 25 in partial 2026, aggregate n at least 300, positive
annual lifts, both aggregate lifts at least 3 points, both Wilson comparisons,
and both all-origin lifts positive.

Passing retrospective gates authorizes only unchanged prospective observation;
it does not change scanner behavior.

## Compute Budget And Stop Rule

- One outcome run over the frozen full universe, at most 8 workers, with one
  BLAS thread per worker.
- Environment order is WSL, Doris, then local fallback. Check memory before the
  run and record the actual environment, workers, and observed memory state.
- Engineering failures before a valid atomic JSON exists may be fixed without
  changing the frozen hypothesis. Preserve invalid partial evidence separately.
- Preserve the valid result as
  `docs/research/results/pmkf-mkf/rsrs-mhpg-full-universe-2021-2026.json` with SHA-256 provenance.
- If any selection or audit gate fails, stop this direction. Do not change the
  18/600 windows, 0.7/0.8 thresholds, parent, label, sample, spacing, or gates;
  do not try XGBoost, HMM, threshold grids, or RSRS combinations.
- Scanner, Web, publisher, watchlist, YAML, and `production_enabled: false`
  remain unchanged.
