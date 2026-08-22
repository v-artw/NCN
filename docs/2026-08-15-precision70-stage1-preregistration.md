# Precision 70 Stage 1 Preregistration

## Economic And Testable Objective

Search for a read-only A-share selection rule whose leakage-safe historical
classification precision is at least 70%. This is not a profit guarantee or a
return backtest. A hit means that within the next five tradable closes, price
reaches at least +3% from T close and never closes below -3% from T close.

A rule with inadequate coverage cannot pass, regardless of apparent precision.

## Fixed Data And Splits

- Deterministic SHA-256 sample of exactly 400 current main-board code files.
- All eligible dates from 2021-01-01 through the observed data end.
- Calibration: 2021-2022. Used only to verify feature availability.
- Selection: 2023-2024. Used to decide whether a candidate may be inspected on
  holdout.
- Holdout acceptance: 2025-2026. Evaluated once with frozen rules.
- Future labels skip suspension rows. An origin becomes historical evidence only
  after its fifth future tradable bar is strictly earlier than prediction date.

## Fixed Baseline And Daily Coverage

- Production-aligned main-board, ST, listing-history, price, ADV20, recent
  trading-day, suspension, and near-limit-up gates apply on T.
- Cross-sectional calculations require at least 150 admitted sample stocks on T.
- `admitted_baseline` is reported but cannot be selected as a strategy.

## Fixed Candidate Library

Exactly three candidates are allowed. They are evaluated independently and are
never combined.

### 1. Breadth Residual Leadership

Market breadth on T among admitted sample stocks:

- At least 60% close above SMA20.
- At least 50% close above SMA60.
- Above-SMA20 breadth is at least 5 percentage points higher than five trading
  dates earlier.
- Cross-sectional median five-day return is positive.

Stock on T:

- Close above SMA20 above SMA60; both averages rise versus T-5.
- Twenty-day return percentile is at least 80% and below 98%.
- Five-day return percentile is at least 60% and below 95%.
- Twenty-day residual return versus `sh.000905` is positive.
- T is bullish; close location is at least 65%; upper shadow is at most 25%.
- Volume/MA20 volume is from 1.0 through 2.5.

### 2. Breadth Pullback Reacceleration

Uses the same fixed breadth regime.

Stock on T:

- Close above SMA20 above SMA60; both averages rise versus T-5.
- Twenty-day return percentile is at least 70% and below 95%.
- Return from T-3 close through T-1 close is between -6% and -1%, inclusive.
- T return versus preclose is from +1% through +5%, inclusive.
- T close is above T-1 high.
- T is bullish; close location is at least 70%; upper shadow is at most 20%.
- Volume/MA20 volume is from 0.9 through 2.2.

No candle-name, oscillator, support-reclaim, or T+1 confirmation is added.

### 3. Barrier-Suitability Prior

For each stock and T:

- Use the latest 252 fully matured prior origins, excluding all labels whose
  fifth tradable-bar maturity date is on or after T.
- Require at least 120 matured origins.
- Posterior propensity is `(prior_hits + 10) / (prior_n + 30)`, a fixed
  Beta(10,20) shrinkage prior centered at one third.
- On each T, posterior propensity must be in the top 5% among admitted stocks
  with adequate history.
- Posterior propensity must be at least 45%.
- T close must be above SMA20, and T five-day return must be between -3% and
  +8%, inclusive, to avoid selecting an already extended bar.

## Frozen Outcome And Metrics

- Label: +3% reached and -3% close floor preserved over T+1 through T+5.
- Report n, hits, false positives, precision, false-positive rate, Wilson 95%
  interval, yearly counts, and signal-date counts.
- Nearby labels are correlated; acceptance also reports results on origins
  spaced at least five trading dates apart per stock as a sensitivity check.

## Frozen Stage 1 Passing Rules

A candidate may reach holdout reporting only if selection 2023-2024 satisfies:

- Precision at least 70%.
- At least 300 matured observations.
- At least 50 observations in both 2023 and 2024.
- Wilson 95% lower bound at least 60%.

Final Stage 1 passes only if the same candidate also satisfies on 2025-2026:

- Precision at least 70%.
- At least 300 matured observations.
- At least 50 observations in 2025 and at least 25 in partial 2026.
- Wilson 95% lower bound at least 60%.
- Precision remains at least 70% in the non-overlapping-origin sensitivity.

More than one candidate may pass. No best-of-three post-hoc combination is
allowed.

## Compute Budget And Stop Rule

- One Stage 1 run, exactly 400 codes, maximum 8 workers and one BLAS thread per
  worker.
- Only candidates passing selection gates are evaluated for acceptance status;
  holdout counts remain in the immutable audit output for transparency.
- A candidate failing any selection or acceptance gate is permanently rejected
  for this historical period. Do not tune thresholds or add variants.
- If no candidate passes, report that no credible 70% strategy was found in the
  available OHLCV/benchmark data and stop this search.
- Only a full Stage 1 pass permits one unchanged all-main-board Stage 2 run.
- Stage 2 pass still requires prospective observation before scanner adoption.
