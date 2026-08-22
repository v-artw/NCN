# Futu Indicator Family Ranking Preregistration

## Objective

Compare every mechanically reproducible bullish indicator family in `futu.md`
under one causal A-share classification protocol. The ranking measures practical
five-tradable-day selection quality, not returns, execution, or profitability.

This document freezes the candidate library, parameters, sample, baseline,
ranking key, gates, and compute budget before the unified outcome run.

## Fixed Confirmatory Candidate Library

Exactly one representative entry trigger is allowed per formula family:

1. `dxbd_cross_zero`: eight-day range position, EMA3 transformation, crossing
   upward through zero. Other DXBD thresholds are state/risk annotations.
2. `ribbon1_strict_buy`: 60-day range position, TDX SMA3 then SMA5 policy-bottom
   line crossing above its SMA8 signal while the signal is below 30.
3. `mhpg_buy`: EMA20 above EMA60, EMA60 rising versus T-1, 30-day KD(3,3)
   bullish cross, and K below 60. Its displayed volume-flow dot is not added.
4. `kdj_trend_pro_buy`: KD(9,3,3) bullish cross, close above EMA60, K below 90.
5. `smc_strong_buy`: close newly breaks the prior 30-day high and the current
   bullish candle body exceeds 70% of its full range.
6. `mkf_green_exit_proxy`: the separately frozen project-local MkF mapping;
   T-1 momentum/inter/near all at or below 20 and T all strictly above 20.
7. `shengbei_long_flip`: fixed 22-day, 3-ATR trailing-wave state changes from
   short to long using deterministic initialization from the first valid state.
8. `gding_bbuy`: EMA6 of typical price crosses above its EMA5 signal.
9. `cpgw_main_long_cross`: the CPGW 34-day EMA4 main line crosses above the
   34-day/MA19 long line while the long line is below 50.

All rolling calculations use tradable stock rows only. Invalid or zero range
denominators produce unavailable values and cannot trigger a signal. A CROSS is
strictly `previous_left <= previous_right AND current_left > current_right`.

## Excluded Or Descriptive Families

- `ALPHAGPT`: excluded because its positive DIV branch sets GATE equal to TREND,
  forcing FACTOR to zero; the prose and emitted trigger do not define one clear
  intended signal.
- Unnamed K/D block: excluded because `P1/P2/P3` are unspecified.
- `KDQ`: excluded because K parameters, second-cross reset, recent-low stop, and
  trend-line exit are prose-only and underdefined.
- MkF's original `BULLCLUSTER`, MHPG `MF_CONFIRM`, SMC liquidity/pivots, GDING
  zones/TREND1/fire-mountain, and CPGW zones are displayed states without a
  source-defined buy entry. The already preregistered MkF exit is explicitly a
  proxy, not claimed as an original MkF trigger.
- Additional thresholds and sub-signals inside DXBD, SMC, GDING, and CPGW are
  correlated components, not separately ranked candidates. This prevents one
  verbose indicator from receiving many opportunities to win.

## Fixed Data And Label

- Exact deterministic SHA-256 sample of 400 current main-board files used by
  Precision 70 Stage 1, preserving the stored code list.
- Every eligible tradable origin from 2021-01-01 through local-data end.
- Calibration 2021-2022 is formula/data-quality reporting only.
- Ranking/selection period: 2023-2024.
- Retrospective audit period: 2025-2026. This period has been inspected in earlier
  studies and is not represented as a pristine holdout.
- Production-aligned code, ST, listing age, price, ADV20, recent-trading-day,
  suspension, and near-limit-up gates apply at T.
- Hit: among the next five tradable closes, at least one reaches +3% from T close
  and none closes below -3% from T close.

## Same-Date Baseline And Primary Observations

- Per-stock origins spaced at least five tradable rows apart are the primary
  ranking observations. All origins are reported as sensitivity.
- On every signal date, calculate precision among all mature production-admitted
  sample stocks. Weight that date's baseline precision by the indicator's signal
  count on the date. This gives signal and baseline identical date weights.
- A date is usable only if at least 150 admitted sample stocks have mature labels.
- Report n, hits, false positives, precision, Wilson 95% interval, same-date
  baseline, lift, signal dates, codes, annual metrics, and trigger coverage.

## Frozen Feasibility And Stability Gates

An indicator is ranking-eligible only if selection 2023-2024 has:

- At least 300 primary non-overlapping observations.
- At least 120 signal dates, at least 50 observations in each year, and signals
  across at least 50 codes.
- Positive point lift in both 2023 and 2024 and aggregate lift at least 3 points.
- Indicator Wilson 95% lower bound above its aggregate same-date baseline.
- All-origin aggregate lift remains positive.

Audit acceptance additionally requires the same aggregate n>=300, annual count
minimums (50 in 2025 and 25 in partial 2026), aggregate lift at least 3 points,
positive annual lifts, Wilson lower bound above baseline, and positive all-origin
lift. Failure cannot promote the next-ranked indicator.

## Frozen Ranking

- Primary ranking key is selection-period non-overlapping precision lift over the
  matched same-date baseline, descending.
- Feasible/stable candidates rank ahead of failed candidates. Within each group,
  sort by the primary key, then indicator ASCII identifier.
- Also report raw precision and Wilson intervals, but do not combine sample size,
  precision, and coverage into an outcome-tuned score.
- Because these correlated formulas and 2025-2026 outcomes have been studied
  previously, the ranking is comparative retrospective evidence. Any winner
  still requires unchanged prospective observation.

## Compute Budget And Stop Rule

- One unified run, exactly 400 codes, at most 8 workers, one BLAS thread each.
  Environment order is WSL, Doris, then local fallback.
- No threshold changes, extra formula variants, additive voting, winner rescue,
  or reranking after outcomes.
- Scanner, Web selection, publisher, and production YAML remain unchanged.
