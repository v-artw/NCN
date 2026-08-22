# T-Open Plus-3 Five-Day Win-Rate Preregistration

## Fixed Hypothesis

The unchanged stock selector (`smc_medium_buy` plus existing hard gates),
calculated after T-1 closes, has a higher probability than the same-date
admitted Main Board baseline of touching `T_open * 1.03` during T+1 through
T+5.

## Fixed Sample And Timeline

- Include every current Main Board Parquet file with a configured prefix and
  every eligible signal origin from 2021-01-01 through the latest local data.
- Signal uses T-1 and earlier rows only. The next stock-tradable row is T and
  its unadjusted-in-file open is the entry reference.
- T high is excluded. Inspect the next five stock-tradable rows after T,
  skipping suspension rows. Fewer than five rows is `pending` and excluded from
  the mature win-rate denominator.
- Win: any T+1..T+5 high is greater than or equal to `T_open * 1.03`.
- Loss: all five eligible highs remain below the target. No stop, alternate
  target, horizon, candidate, or post-hoc exclusion is permitted.

## Reports And Decision Rules

- Report mature n, wins, losses, win rate, Wilson 95% interval, signal dates,
  entry dates, and codes for full history, each year, 2021-2023 selection, and
  2024-present audit.
- Same-entry-date baseline is every hard-gate-admitted Main Board stock with a
  mature path, weighted by selector candidate count. Baseline dates require at
  least 150 mature admitted stocks.
- Report lift over baseline and pending/invalid coverage. The result describes
  target-touch classification only, not realized profit.
- Interpret as stable selection evidence only if selection and audit each have
  n>=300, >=120 entry dates, >=50 codes, win-rate lift >=3 percentage points,
  Wilson lower bound above baseline, and every complete year has positive lift.
- One full-universe run, maximum 8 workers, one BLAS thread per worker. Attempt
  WSL, then Doris, then local.

## Boundaries

Daily high touching the target does not prove a queued sell order filled. T open
does not prove a buy fill. No fees, tax, slippage, T+5 fallback exit, capital,
position, return, or P&L is modeled. Therefore this study can answer the fixed
target-touch win rate, but cannot by itself establish profitability.
