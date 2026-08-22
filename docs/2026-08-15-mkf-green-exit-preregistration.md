# Strict MkF Green-Zone Exit Preregistration

## Question And Frozen Signal

Test the user's exact hypothesis that MkF becomes an effective A-share review
signal when it has just left the green oversold zone and all three lines have
crossed above 20.

The origin is T. The signal is true only when:

- At T-1, `MOMENTUM <= 20`, `INTER <= 20`, and `NEAR <= 20`.
- At T, `MOMENTUM > 20`, `INTER > 20`, and `NEAR > 20`.
- T is a tradable, production-admitted stock date.

This strict same-day transition is frozen before outcomes. Do not reinterpret it
as any line crossing, two-of-three recovery, a recent oversold lookback, or lines
that merely remain above 20.

## Frozen Formula Parameters

`futu.md` does not provide numeric values for `MEDLEN`, `NEARLEN`, or `MOMLEN`.
Use the project-local MkF mapping already implemented before this study:

- `INTER = MA((C - LLV(L, 20)) / (HHV(H, 20) - LLV(L, 20)) * 100, 5)`.
- `NEAR = MA((C - LLV(L, 15)) / (HHV(H, 15) - LLV(L, 15)) * 100, 2)`.
- `MOMENTUM = (C - LLV(L, 2)) / (HHV(H, 4) - LLV(L, 4)) * 100`.

All rolling windows use tradable stock rows only. A zero or invalid denominator
makes the line unavailable and cannot create a signal. Only data through T may
enter any line.

## Frozen Data, Label, And Splits

- Exact deterministic SHA-256 sample of 400 current main-board files used by the
  prior Precision 70 Stage 1.
- Every eligible tradable origin from 2021-01-01 through local-data end.
- Selection: 2023-2024. Holdout: 2025-2026, inspected once with unchanged rules.
- Production-aligned code, ST, listing age, price, ADV20, recent-trading-day,
  suspension, and near-limit-up gates apply at T.
- Hit label: among the next five tradable closes, at least one reaches +3% from T
  close and none closes below -3% from T close.
- Baseline: all production-admitted observations on the same signal dates. This
  controls for the market environment in which MkF exits occur.

## Frozen Effectiveness Gates

The signal is considered historically effective only if all gates pass:

- At least 300 matured signal observations in selection and 300 in holdout.
- At least 50 observations in each of 2023, 2024, and 2025, and at least 25 in
  partial 2026.
- Signal precision is at least 3 percentage points above the same-date admitted
  baseline in both selection and holdout.
- Signal Wilson 95% lower bound is above same-date baseline precision in both
  periods.
- Per-stock origins spaced at least five tradable dates apart retain positive
  precision lift in both periods.

The 70% target is reported but is not required for this narrower effectiveness
question. Passing these gates would support a research prompt, not profitability,
orders, or scanner promotion.

## Budget And Stop Rule

- One Stage 1 run over exactly 400 codes, at most 8 workers, one BLAS thread per
  worker. Test environment order is WSL, Doris, then local fallback.
- Report period/year counts, hits, false positives, precision, Wilson interval,
  same-date baseline, and non-overlap sensitivity.
- If any gate fails, conclude that this strict MkF green-zone exit lacks stable
  historical effectiveness. Do not change parameters, use a recent-lookback exit,
  relax to two lines, or add MHPG/DXBD filters on this historical sample.
