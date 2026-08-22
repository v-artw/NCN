# Bullish Engulfing Confirmation Stage 1 Preregistration

## Objective

Test one Nison-inspired, mechanically frozen candidate: a bullish engulfing
line at rising SMA20 support inside an established SMA20/SMA60 uptrend, followed
by a next-trading-day close confirmation. This is a classification study, not a
return, execution, or profit backtest.

## Fixed Signal

At origin day T, all calculations use data through T only:

- `close > SMA20 > SMA60`; SMA20 is strictly above its T-5 value and SMA60 is
  strictly above its T-5 value.
- Twenty-trading-day close return is between +3% and +30%, inclusive.
- T low is at or below `SMA20 * 1.01`, while T close is at or above SMA20.
- T-1 is bearish with body/range at least 35%.
- T is bullish, its body is at least 1.10 times T-1 body, its real body covers
  the T-1 real body, and T close is at or above T-1 open.
- T-1 volume is below the median volume of the preceding 20 rows; T volume is
  strictly above T-1 volume and at least that same median.
- T and T+1 are consecutive traded rows with positive volume. T+1 close is
  strictly above T close and at or above T low. Only then is the candidate
  confirmed and published for research review.

The engulfing geometry follows the source pattern, while all numeric thresholds
and the SMA/support/volume context are project-defined mappings. No KDJ,
Shengbei, MHPG, hammer, piercing, pattern voting, or parameter variants are
allowed.

## Baseline, Label, And Gates

- Baseline: on the same T dates, all mature production-admitted stock rows that
  satisfy the same SMA20/SMA60 trend, return, support, T-1 bearish/light-volume
  context, and have a valid T+1 row. It does not require engulfing or
  confirmation. Baseline and candidates are evaluated from T+2 through T+6.
- Hit: at least one close reaches +3% from the T+1 confirmation close and no
  close is below -3% during T+2 through T+6. Exactly five future traded closes
  are required.
- Stage 1 uses the exact SHA-256 400-code sample already used by Precision 70,
  2021-01-01 through local data end; 2023-2024 is selection and 2025-2026 is
  retrospective audit. Primary observations are spaced at least five traded
  rows per code; all-origin sensitivity is reported.
- Selection requires primary n>=300, n>=50 in each year, at least 120 signal
  dates and 50 codes, positive annual lifts, aggregate lift>=3 points, Wilson
  lower bound above the matched same-date baseline, and positive all-origin
  lift. Audit requires the same aggregate/annual/Wilson gates with 2025 n>=50
  and partial 2026 n>=25.
- One Stage 1 run only. Any failed gate stops this direction; no threshold
  relaxation, alternate candle, or full-universe follow-up is authorized.

## A-Share Data Rules And Budget

- Current main-board Parquet files only; adjusted research OHLCV is used for
  classification, so corporate-action and true-gap limitations remain explicit.
- Suspended rows cannot be T or T+1; no compression across suspension is used.
- Existing production admission gates apply at T. `production_enabled` remains
  false and no scanner behavior changes.
- Run WSL first, Doris second, local last; maximum 8 workers and one BLAS
  thread. Use one fixed 400-code run before any implementation decision.
