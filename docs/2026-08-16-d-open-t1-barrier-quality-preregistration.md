# D-Open T+1 Barrier-Path Quality Preregistration

## Fixed Hypothesis And Candidate Set

- Test unchanged `smc_medium_buy`, `smc_bull_bos`, and
  `kdj_trend_pro_buy`. Do not add combinations, tune thresholds, or substitute
  another signal after outcomes.
- Preserve rolling causality: each signal uses rows visible through origin T
  only. Entry reference is the next tradable day D open. D OHLCV is outcome-only.
- This is read-only signal-quality research. It does not model an order, fill,
  position, capital allocation, cost, realized return, or personalized action.

## A-Share T+1 And Path Rules

- Because a D purchase cannot be sold on D, eligible barrier observation begins
  on D+1. The 5-day window is D+1 through D+5 and the 10-day window is D+1
  through D+10, counting stock-tradable rows and skipping suspensions.
- Anchor every barrier to D open. Report D-open gap versus T close and whether D
  high touched +3%/+5%; these D-day touches are unavailable for exit.
- Report MFE from eligible highs and MAE from eligible lows.
- Evaluate `+3%` against `-3%` and `+5%` against `-5%`. For each pair, scan days
  in order. First target-only day is `target_first`; first risk-only day is
  `risk_first`; both crossed on the first event day is `same_day_ambiguous`;
  neither is `neither`. Daily OHLC cannot resolve the ambiguous intraday order.
- Exact target/risk equality counts as touched for this barrier study.

## Baseline, Reports, And Frozen Gates

- Use all 3,196 current-main-board files and every mature origin. Primary results
  do not de-overlap observations.
- Compare candidate `target_first` and `risk_first` rates with same-D admitted
  stocks, weighted by candidate count; require at least 150 mature rows on D.
- Report all-history, annual, 2021-2023 selection, and 2024-present audit periods,
  plus MFE/MAE quantiles, D-gap quantiles, D-day unavailable touches, and the
  incremental target-first recovery from 5 to 10 days among 5-day unresolved
  observations.
- A candidate/barrier is quality-supported only if selection and audit each have
  `n >= 300`, at least 120 D dates, target-first lift >=3 percentage points,
  candidate Wilson lower bound above baseline, positive complete-audit-year
  target-first lift, and no increase in risk-first rate versus baseline in either
  period. Ambiguous cases remain separate and never count as successful.
- One full run, maximum 8 workers and one BLAS thread each. Attempt WSL, then
  Doris, then local.
