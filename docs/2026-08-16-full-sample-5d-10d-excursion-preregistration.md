# Full-Sample 5/10-Day Intraday Excursion Preregistration

## Hypothesis And Alignment

- Preserve the user's rolling method: signals for origin T use data visible
  through T only. Outcomes begin on the stock's next tradable day D; suspension
  rows are skipped.
- Use every current-main-board stock file and every mature origin date. Do not
  sample stocks or dates and do not de-overlap primary observations.
- Anchor both horizons to T close. For the next 5 and next 10 tradable rows,
  respectively, use the maximum observed daily high.
- `pass_3pct` is true only when maximum high is strictly above `T close * 1.03`.
  `full_5pct` is true when maximum high is greater than or equal to
  `T close * 1.05`. A full-score observation also counts as passing.
- Exclusive score is 0 below/equal to 3%, 1 above 3% but below 5%, and 2 at or
  above 5%.

## Candidates And Baselines

- Reuse unchanged objective `futu.md` and Nison-informed candlestick masks from
  the direct-next-day study. Do not tune formula or candle thresholds.
- Underdefined unnamed KD and KDQ prose remain excluded; do not guess values.
- For each horizon and threshold, compare with the same-D admitted-stock outcome
  rate, weighted by that candidate's count. Require at least 150 mature baseline
  rows for D.
- Bullish candidates improve when their rate is above baseline. Risk candidates
  improve when their upward-excursion rate is below baseline. Annotation states
  are descriptive only.

## Frozen Decision And Budget

- Report all-history, yearly, 2021-2023 selection, and 2024-present audit results.
- A bullish or risk candidate passes a horizon/threshold only when both selection
  and audit have `n >= 300`, at least 120 target dates, directional improvement
  of at least 3 percentage points, and the candidate Wilson interval is separated
  from baseline in the expected direction. Every complete audit year must have
  positive directional improvement.
- Maximum budget is one full 3,196-code run with at most 8 workers and one BLAS
  thread each, attempted WSL then Doris then local.
- This is read-only excursion classification, not orders, positions, execution,
  costs, realized returns, P&L, or personalized advice.
