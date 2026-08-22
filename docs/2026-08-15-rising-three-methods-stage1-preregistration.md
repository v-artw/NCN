# Strict Rising Three Methods Stage 1 Preregistration

## Decision Objective

Test whether a strict, fully completed rising-three-methods continuation
pattern improves short-horizon selected-stock precision over stocks with the
same market and individual-trend context. This is a bounded implementation
decision, not an open-ended pattern search.

## Frozen Universe And Sample

- Current local main-board files admitted by the production universe gates.
- Deterministic SHA-256 sample of exactly 400 codes.
- Every eligible signal date from 2021-01-01.
- Calibration: 2021-2024.
- Holdout acceptance: 2025-2026.
- One Stage 1 run only. Stage 2 may use all current main-board files only if
  every Stage 1 threshold passes.

## Frozen Comparison Baseline

`trend_context_baseline` contains all admitted stock dates satisfying the same
market regime and individual-stock trend rules below. It does not require a
candle pattern. The strict pattern is compared only with this contemporaneous
context baseline.

## Frozen Market Regime

Using `sh.000001` through T only:

- T close is above SMA20.
- SMA20 at T is not below SMA20 at T-5.
- Five-trading-day benchmark return is at least -3%.

Missing benchmark dates fail the regime gate.

## Frozen Individual Trend

Using stock data through T only:

- `close[T] > SMA20[T] > SMA60[T]`.
- `SMA20[T] > SMA20[T-5]` and `SMA60[T] > SMA60[T-5]`.
- Twenty-trading-day close return is between +5% and +25%, inclusive.

## Frozen Pattern Definition

The final completion candle is T. The first impulse candle is followed by a
consolidation of exactly 2, 3, or 4 candles, so pattern lengths are 4, 5, or 6
bars. If more than one length matches on T, count T once and report the longest
matching consolidation.

### First Impulse Candle

- Bullish close.
- Real body is at least 55% of the full high-low range.
- Close location is at least 75% of the full range.
- Volume is at least its trailing 20-bar mean through the impulse candle.

### Consolidation Candles

- Every full high-low range is inside the first impulse candle's high-low
  range; no tolerance is added.
- Every real body is at most 40% of the first impulse real body.
- At least half of the consolidation candles close no higher than their
  preceding candle, implementing the source's falling-group context.
- Every consolidation candle volume is lower than the impulse candle volume.
- Median consolidation volume is lower than the impulse candle volume.

### T Completion Candle

- Bullish close.
- Opens strictly above the preceding consolidation candle's close.
- Closes strictly above the first impulse candle's close.
- Real body is at least 55% of its full range.
- Close location is at least 65% of its full range.
- Upper shadow is at most 20% of its full range.
- Volume is strictly above median consolidation volume.
- Volume is no more than 2.8 times its trailing 20-bar mean through T.
- Existing production gates exclude ST, suspension, low liquidity, invalid
  price, insufficient history, and near-main-board-limit-up completion bars.

No near-complete variant, T+1 rescue confirmation, gap relaxation, oscillator,
MHPG, DXBD, discovery score, or additional filter is allowed in Stage 1.

## Frozen Outcome Label

For both baseline and strict pattern, relative to T close:

- Observe stock closes T+1 through T+5.
- Hit when at least one observed close is at least +3% and no observed close is
  below -3%.

T+1 through T+5 are outcomes only and cannot affect pattern detection.

## Frozen Success Thresholds

The strict pattern passes Stage 1 only if every condition holds:

- Precision is above the context baseline in both calibration and holdout.
- Aggregate precision lift across 2021-2026 is at least 3 percentage points.
- Relative false-positive-rate reduction is at least 10% in both calibration
  and holdout.
- At least 150 matured strict-pattern observations in both calibration and
  holdout.
- At least 50 matured observations in each complete year 2021-2025. The partial
  2026 year is reported but has no annual minimum.
- Strict-pattern 95% Wilson lower bound is not below the context-baseline
  precision in either calibration or holdout.

## Stop And Implementation Decision

- Any failed threshold stops this direction immediately. Do not change pattern
  thresholds, add relaxed variants, or rerun the same sample.
- Stage 1 pass permits one all-main-board Stage 2 run with unchanged code and
  thresholds.
- Stage 1 failure keeps all code research-only and leaves tagged V1 runtime
  unchanged.
- Stage 2 pass permits a separately reviewed v2 runtime implementation; it does
  not authorize orders, portfolio/P&L, execution, or a profit claim.

## Compute Budget

- Maximum 8 worker processes, one BLAS thread per worker.
- WSL first, Doris second, local last according to project policy.
- No internet indicator search or additional historical mining during this
  Stage 1 decision.
