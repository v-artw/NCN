# SMC Stock Selector Contract

## Purpose

Provide a usable, read-only stock-selection command from existing local daily
bars. It does not require paid intraday data and does not model orders, fills,
positions, returns, or P&L.

## Fixed Selection Rule

- Universe and hard gates come unchanged from `yaml/edge_scout_v1.yaml`:
  Main Board prefixes, non-ST, at least 252 rows, CNY 5-80 close, at least 55
  tradable rows in 60, ADV20 at least CNY 100m, tradable T, and no near-limit-up
  T close.
- Primary signal is unchanged `smc_medium_buy`: on tradable rows, T low is
  strictly above T-2 high and EMA20 is strictly above EMA50.
- The selector runs after the signal session closes. Its latest visible row is
  named `signal_date` (T-1 in the user's intended timeline). The next trading
  session is the intended T entry-reference session, whose observed open will
  anchor the later target study.
- Automatic `signal_date` is the latest date observed in local Parquet. A stock
  must contain a row exactly on that date; stale files are not silently
  evaluated on an earlier date.
- A manual `--as-of` supplies `signal_date` and truncates every stock to that
  date. Later rows cannot affect selection or annotations.
- The later fixed contract is descriptive and not implemented in this first
  step: T open as entry reference, then T+1 through T+5 observe whether high
  reaches `T_open * 1.03`. T-day high does not count because A-share shares
  acquired on T cannot be sold on T.

## Output And Ordering

- Every selected candidate is written to immutable per-run CSV and JSON files.
- Console `--top` limits display only; it never drops rows from saved output.
- Review order is deterministic: fewer risk warnings first, then greater T-day
  amount, then code. This is an ergonomic review order, not a learned rank or
  probability.
- Explainable fields include close, amount, turnover, SMC gap size, EMA20/EMA50,
  and warning codes.
- Fixed warning annotations are `kdj_trend_pro_sell`, `mkf_bearcluster`, and
  `candle_tweezer_top`. They prompt human review and do not create short/sell
  instructions or alter the primary selection rule.
- This selector does not call T open a fill and does not claim the later +3%
  target will be reached. Unreached observations, costs, and exit handling are
  outside this first-step output and must not be omitted from any later profit
  assessment.

## Acceptance

- Synthetic tests must prove exact SMC boundaries, hard-gate exclusion,
  post-T causality, warning-only behavior, all-candidate persistence, and atomic
  immutable publication.
- A local real-data smoke run must complete with strict JSON, quantity counts,
  no source-data writes, and no unexpected errors before the command is treated
  as usable.
