# CNInfo Earnings Forecast/Express PDF Coverage Probe Preregistration

## Hypothesis

CNInfo's official announcement archive can support a later point-in-time, research-only MHPG filter by preserving enough first-publication earnings forecast/express PDFs to identify events whose disclosed parent net-profit lower bound is positive and whose lower-bound year-over-year growth is at least 30%. Corrections are not initial admissions; each original, correction, and supplement remains a separate immutable document event, with correction links inferred only when issuer, reporting period, document type, and explicit correction language agree.

## Frozen Probe

- Source: CNInfo historical-announcement metadata and linked CNInfo PDFs, using the request contract reviewed from AKShare commit `1248fdd05a2dda92937d4cd39c0957825f2f7f6e`.
- Codes: the fixed first 40 codes selected by SHA-256 of the eligible six-digit code stem, displayed here in numeric order: `600000`, `600021`, `600025`, `600031`, `600052`, `600055`, `600085`, `600096`, `600100`, `600105`, `600132`, `600148`, `600161`, `600162`, `600166`, `600169`, `600176`, `600192`, `600196`, `600216`, `600223`, `600229`, `600248`, `600255`, `600276`, `600282`, `600284`, `600295`, `600301`, `600307`, `600323`, `600339`, `600340`, `600348`, `600354`, `600356`, `600360`, `600368`, `600375`, `600397`.
- Date range: `2021-01-01` through `2026-08-15`, inclusive.
- Retrieval: complete pagination, one worker, at most 500 PDFs and at most 2 GB total PDF bytes.
- Archive: ignored `.runtime/` only, with normalized metadata, retrieval timestamps, source URLs, immutable announcement IDs, PDF SHA-256 hashes, and raw PDFs.
- Parsing: `pdftotext` only. Accept a first-publication event only when one unambiguous reporting period, parent net-profit lower bound, and lower-bound YoY growth are explicitly attributable to the forecast/express disclosure. Reject missing, conflicting, multi-period, OCR-corrupted, inferred, or otherwise ambiguous fields. Do not derive growth from price data or inspect any future price label.
- Corrections: preserve every document as a separate announcement ID. Retain a correction chain only when explicit correction wording and matching issuer, reporting period, and forecast/express type identify one unique earlier original; otherwise leave the document unlinked.

## Pass Gates

The probe passes only if all gates hold without post-observation relaxation:

- At least 30 of 40 codes have covered earnings forecast/express announcements.
- Every full calendar year 2021, 2022, 2023, 2024, and 2025 has at least one parseable first-publication event.
- At least 120 first-publication events are conservatively parseable.
- At least 10 correction chains are separately retained and conservatively linked.
- At least 95% of covered announcement rows have complete provider timestamp and required parsed fields.
- A repeated complete normalized metadata retrieval has the same SHA-256 hash.

## Decision And Budget

- Pass: archive the probe result and permit a separately preregistered evaluation of the single frozen MHPG filter.
- Fail or parser ambiguity: stop this direction. Do not loosen parsing rules, categories, sample, dates, thresholds, or correction linkage after observing coverage.
- Maximum budget: 40 codes, complete metadata pagination twice for stability, 500 PDFs, 2 GB, one worker. No backtest, return calculation, scanner/runtime integration, or price-label inspection is authorized.
