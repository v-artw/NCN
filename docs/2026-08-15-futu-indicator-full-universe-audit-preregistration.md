# Futu Indicator Full-Universe Audit Preregistration

## Objective

Run the already frozen `futu.md` nine-family comparison over every current local
main-board Parquet file from 2021 through the observed 2026 data end. Compare the
result with the deterministic 400-code Stage 1 ranking to measure sample
sensitivity. This audit cannot change formulas, thresholds, gates, or ranking
rules and is not a return/profit backtest.

## Frozen Universe And Logic

- Include every current file with prefixes `sh.600`, `sh.601`, `sh.603`,
  `sh.605`, `sz.000`, `sz.001`, `sz.002`, or `sz.003`.
- Sort by code and record the exact code count, code list, and SHA-256 of the
  newline-delimited code list in the result. The current expected count is 3,196;
  any different count is reported and must still remain immutable for the run.
- Preserve all definitions from
  `docs/2026-08-15-futu-indicator-ranking-preregistration.md`: nine family
  representatives, production gates, suspension-aware five-close label,
  per-stock five-tradable-index spacing, indicator-specific signal-count-weighted
  same-date baseline, `>=150` mature admitted rows per date, feasibility gates,
  and 2023-2024 selection-lift ranking.
- Calibration is 2021-2022, ranking is 2023-2024, and 2025-2026 is retrospective
  audit only. No full-universe outcome may alter a formula or promote a failed
  runner-up.

## Frozen Difference Report

After completion compare full universe with the stored 400-code result:

- Rank and rank-position change for all nine families.
- Selection and audit n, precision, matched baseline, and lift changes.
- Eligibility/audit-decision changes and annual-lift sign changes.
- Whether the 400-code top-ranked family remains top-ranked.
- Whether any full-universe candidate passes all unchanged gates.

Differences are evidence about sample sensitivity, not permission to choose the
better of two samples.

## Doris Resource And Persistence Budget

- Run on Doris managed Python 3.13 with 8 worker processes and
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and
  `NUMEXPR_NUM_THREADS=1`.
- Verify memory pressure before launch. Do not exceed 8 workers because the full
  panel is memory-heavy and Doris also hosts the omlx service.
- Launch under `nohup` with stdin detached. Persist PID, log, atomic result path,
  and a separate exit-status file under remote ignored `.runtime/`.
- SSH disconnection must not terminate the evaluator. A later session can inspect
  PID liveness, log progress, exit status, result existence, and result SHA-256.
- One full-universe run only. Do not restart while its PID is live. A process
  failure may be resumed only by a fresh unchanged run because this evaluator has
  no stock-level checkpoint contract.
