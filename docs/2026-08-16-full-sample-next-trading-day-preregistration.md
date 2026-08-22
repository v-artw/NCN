# Full-Sample Next-Trading-Day Validation Preregistration

## Actionable Hypothesis

Signals explicitly and causally computable from `futu.md`, plus fixed
Nison-informed candlestick patterns, may classify the direction of the next
tradable close more precisely than the same-date eligible-stock direction rate.

## Frozen Alignment And Sample

- Use every local current-main-board Parquet file accepted by NCN's fixed code
  prefixes. Do not sample stocks or dates.
- For every tradable origin T, compute signals using rows visible through T only.
- The target D is that stock's next row with `tradestatus == 1`; suspension rows
  are skipped. No D OHLCV field may enter a T signal.
- A bullish signal hits iff D close is strictly greater than T close. A bearish
  risk signal hits iff D close is strictly less than T close. A flat close is a
  miss for both directions.
- Report every available target year and one aggregate covering the complete
  local history. Primary observations include every origin; a five-trading-row
  spaced report is sensitivity only.
- Compare each signal with the same-target-date direction rate among all stocks
  admitted at T. Weight date baselines by that signal's candidate count and
  require at least 150 comparable rows on a target date.

## Frozen Candidate Handling

- Evaluate every objective Futu trigger/state already mapped by the project,
  including the nine family representatives and explicit buy, sell, risk, and
  state annotations in `futu.md`.
- Evaluate the fixed bullish and bearish reversal patterns in
  `ashare_edge_scout.candles` plus the already-defined project-local Nison
  geometries. Numerical geometry is project-defined, not attributed verbatim to
  Nison.
- Do not invent missing `P1/P2/P3`, KDQ second-cross/stop/trend-line mechanics,
  or any other underdefined formula. List each exclusion in the result.
- Do not tune formulas, thresholds, contexts, or pattern combinations after
  observing results.

## Decision Gates And Budget

- Descriptive success for a directional candidate requires, separately in
  2021-2023 and 2024-present: `n >= 300`, at least 120 target dates, precision
  lift of at least 3 percentage points, and its 95% Wilson lower bound above the
  matched baseline. Every complete audit year must have positive lift.
- Failure means reject scanner promotion and stop threshold variants on this
  historical sample. Passing remains retrospective evidence and requires
  unchanged prospective confirmation.
- Maximum compute: one full-universe run, at most 8 workers, one BLAS thread per
  worker. Test environments are attempted WSL, then Doris, then local.
- This is read-only direction classification. It does not calculate returns,
  costs, orders, positions, capital, P&L, or execution.

## Default Method Contract

This T-to-next-tradable-D alignment and direct D-realized comparison is NCN's
default historical validation method for later research unless the user
explicitly requests another method. The method is also recorded in the newest
`HANDOFF.md` entry for cross-session continuity.
