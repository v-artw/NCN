# Point-In-Time Industry Breadth Stage 1 Preregistration

## Objective And Hypothesis

Test whether effective-dated industry membership plus same-date industry breadth
can isolate a read-only A-share candidate set with at least 70% five-tradable-day
classification precision. This is not a profit, execution, or return backtest.

The fixed hypothesis is that a production-admitted MHPG recovery signal is more
reliable when its stock belongs to a broad industry advance rather than moving
without industry confirmation.

## Source And Point-In-Time Contract

- Industry records come only from CNInfo `p_stock2110`, as implemented by the
  MIT-licensed AKShare `stock_industry_change_cninfo` adapter.
- Archive normalized records with stock code, classification standard and code,
  industry names, effective change date, source URL, retrieval timestamp, and a
  SHA-256 hash of the raw provider response.
- At T, use only the latest record whose effective change date is on or before T.
- Use the provider's `证监会行业分类标准` record and the most specific non-empty
  industry code/name available. No current constituent list may be projected
  backward.
- An effective date is usable at T because the record describes classification
  membership, not an after-close trading signal. Records with missing or invalid
  effective dates are unusable.

## Frozen Coverage Probe

- Probe the first 40 codes from the existing deterministic SHA-256 400-code
  sample, sorted by code after sampling.
- Query each code once for 2015-01-01 through 2026-08-15.
- Maximum budget: 40 requests, one worker, bounded retries, and 10 minutes.
- Pass only if at least 38 of 40 codes have a valid classification record
  effective on or before 2021-01-01, every accepted record has a valid effective
  date and classification identity, and a repeated fixed-code request has the
  same normalized content hash.
- A failed probe permanently stops this direction before historical outcomes are
  evaluated. Do not change the sample, coverage threshold, classification
  standard, or date range after observing probe results.

## Fixed Stage 1 Data And Splits

- The exact deterministic SHA-256 sample of 400 current main-board Parquet files.
- All eligible origins from 2021-01-01 through the observed local-data end.
- Selection: 2023-2024. Holdout acceptance: 2025-2026, inspected once only after
  rules are frozen and reported even when selection fails as an audit result.
- Future labels skip suspension rows: within T+1 through T+5 tradable closes,
  price reaches at least +3% from T close and no close falls below -3%.
- Production-aligned universe gates apply at T.

## Fixed Baseline And Candidate

Baseline:

- `admitted AND mhpg_buy` on the same dates and codes for which the candidate has
  valid industry membership and an adequate industry denominator.

Exactly one candidate is allowed:

- Baseline signal is true.
- At least 10 sampled, production-admitted stocks share the signal stock's
  effective industry on T.
- At least 60% of those industry members close above SMA20 on T.
- Industry above-SMA20 breadth is strictly higher than five valid sample trading
  dates earlier.
- The cross-sectional median five-day return of those members is positive.

Membership and breadth use all eligible stocks in the frozen 400-code sample,
not only stocks with MHPG signals. No alternate denominator, threshold, industry
level, candidate combination, or missing-value imputation is permitted.

## Frozen Passing Rules

Selection 2023-2024 must satisfy all of:

- Candidate precision at least 70%.
- At least 300 matured observations and at least 50 in each full year.
- Wilson 95% lower bound at least 60%.
- Precision at least 3 percentage points above the same-date MHPG baseline.
- Relative false-positive reduction versus that baseline at least 20%.

Holdout 2025-2026 must independently satisfy all of:

- Candidate precision at least 70%.
- At least 300 matured observations, at least 50 in 2025, and at least 25 in the
  partial 2026 year.
- Wilson 95% lower bound at least 60%.
- Precision at least 3 percentage points above the same-date MHPG baseline and
  relative false-positive reduction at least 20%.
- Per-stock origins spaced by at least five tradable dates retain at least 70%
  precision.

## Compute Budget And Decision

- After a passing probe: one 400-code Stage 1 run, at most 8 workers and one BLAS
  thread per worker. WSL, Doris, then local environment priority applies.
- No full-universe Stage 2 is allowed unless every Stage 1 gate passes unchanged.
- Failure stops this industry-breadth direction. Do not mine industry levels,
  breadth windows, thresholds, MHPG variants, or additional filters on the same
  historical period.
- A Stage 1 pass is evidence for a prospective read-only observation candidate,
  not proof of profitability and not authorization to change scanner runtime.
