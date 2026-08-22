# CNInfo Risk-Disclosure Exclusion Stage 1 Preregistration

## Objective And Hypothesis

Test whether excluding recent official risk disclosures can raise a read-only
A-share MHPG candidate set to at least 70% five-tradable-day classification
precision. This is not a profit, execution, or return backtest.

The fixed hypothesis is that recent issuer risk, correction, clarification, or
special-treatment disclosures identify avoidable false positives that price and
volume indicators alone do not represent reliably.

## Frozen Source And Categories

- Source: CNInfo historical-announcement endpoint used by the MIT-licensed
  AKShare `stock_zh_a_disclosure_report_cninfo` adapter.
- Exactly four CNInfo categories are included: `补充更正` (`category_bcgz_szsh`),
  `澄清致歉` (`category_cqdq_szsh`), `风险提示` (`category_fxts_szsh`), and
  `特别处理和退市` (`category_tbclts_szsh`).
- Do not add title keywords, reinterpret titles, scrape PDF text, or add/remove
  categories after observing results.
- Archive announcement ID, code, organization ID, title, provider timestamp,
  category queried, source URL, retrieval timestamp, and normalized-content
  SHA-256. Deduplicate by announcement ID.

## Point-In-Time Availability

- Provider timestamps are interpreted in Asia/Shanghai.
- Because the historical endpoint may expose a date or midnight rather than the
  exact exchange publication time, every announcement becomes usable only on the
  next tradable stock date after its provider calendar date. This also handles
  after-close publication conservatively.
- A candidate at T is excluded when at least one fixed-category announcement has
  an availability date in the latest 10 tradable stock dates through T.
- Missing, invalid, or future provider timestamps are unusable; no report-period
  or retrieval-date substitution is allowed.

## Frozen Coverage Probe

- Probe the same first 40 codes from the deterministic SHA-256 400-code sample
  used by the stopped industry probe.
- Query all four fixed categories for 2021-01-01 through 2026-08-15, with complete
  pagination. Maximum budget: 160 category-code queries, one worker, two retries,
  and 20 minutes.
- The probe passes only if all 40 codes exist in the provider stock map, every
  response has a valid total and announcement list, every returned row has an
  announcement ID, matching code, valid provider timestamp, and category
  provenance, and a repeated fixed query has an identical normalized hash.
- It must observe at least 40 distinct fixed-category announcements across at
  least 15 sample codes, with at least one announcement in each of 2021, 2022,
  2023, 2024, and 2025. These are availability gates, not strategy outcomes.
- Probe failure stops this direction before historical labels are evaluated. Do
  not change the category set, sample, years, or coverage gates after results.

## Fixed Stage 1 Data And Candidate

- Exact deterministic SHA-256 sample of 400 current main-board code files and all
  eligible origins from 2021-01-01 through the observed local-data end.
- Production-aligned universe gates apply at T. Future labels skip suspensions.
- Hit label: within T+1 through T+5 tradable closes, price reaches at least +3%
  from T close and no close falls below -3%.
- Selection is 2023-2024. Holdout acceptance is 2025-2026 and is inspected once.

Baseline:

- `admitted AND mhpg_buy` on the same code-date source coverage as the candidate.

Exactly one candidate:

- Baseline is true and no fixed-category risk disclosure is available during the
  latest 10 tradable stock dates through T.

No alternate lookback, MHPG variant, title sentiment, event weighting, event
count threshold, or additional price/fundamental filter is allowed.

## Frozen Passing Rules

Selection 2023-2024 and holdout 2025-2026 must each independently satisfy:

- Candidate precision at least 70%.
- At least 300 matured observations; at least 50 in each full year, plus at least
  25 in partial 2026.
- Wilson 95% lower bound at least 60%.
- Precision at least 3 percentage points above the same-coverage MHPG baseline.
- Relative false-positive reduction versus baseline at least 20%.
- Per-stock origins spaced by at least five tradable dates retain at least 70%
  precision in holdout.

## Compute Budget And Decision

- After a passing probe: one 400-code Stage 1 run, at most 8 workers and one BLAS
  thread per worker. Environment order remains WSL, Doris, then local.
- No all-main-board Stage 2 unless every Stage 1 gate passes unchanged.
- Failure permanently stops this risk-disclosure direction for this historical
  period. It cannot be rescued by category, keyword, or lookback mining.
- A Stage 1 pass permits only a proposal for prospective read-only observation;
  it does not prove profitability or authorize scanner-runtime integration.
