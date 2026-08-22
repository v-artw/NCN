# Staged-Target Data Acquisition Gate

## Status

Blocked on user-controlled credentials and a paid-data decision. No dataset was
downloaded, no service was purchased, and no model or outcome was evaluated.
This gate must be satisfied before implementing the staged-target study in
`2026-08-16-internet-informed-staged-target-solution.md`.

## Actionable Hypothesis

For unchanged `smc_medium_buy` observations, unadjusted opening-auction and
09:30-09:35 one-minute data can identify opening-quality states that improve the
precision of the five-day target-first label without increasing adverse-first
outcomes. Minute bars can establish only a conservative research reference,
not whether a hypothetical order filled in a price-time-priority queue.

## Candidate Source Decision

Tushare is the only inspected source with public documentation that names all
of the following separately accessible fields needed for a bounded first
study:

- A-share `1min` OHLC, traded volume, and amount, with more than ten years of
  history documented by `stk_mins`;
- opening-auction price, volume, amount, and VWAP from `stk_auction_o`;
- daily up-limit, down-limit, and previous-close values from `stk_limit`;
- dated suspension and resumption records from `suspend_d`.

Its published individual pricing currently lists historical A-share minute
permission at RMB 2,000/year and collection-auction permission at RMB 500.
Company/institution pricing is documented as ten times individual pricing.
These are external, non-refundable purchases and are not authorized by this
document.

The service agreement grants a personal, non-transferable, non-commercial,
time-limited licence and requires official access methods. Therefore any
credential must remain outside Git, raw data must not be redistributed, and
licence compatibility must be confirmed for the actual account and intended
reviewers before acquisition. Published docs do not promise immutable
historical vintages, so fetched files need retrieval timestamps, request
parameters, response hashes, and later revision checks.

Other inspected paths are not accepted for this study:

- Existing Eastmoney `1m` data is limited to recent days and its adapter warns
  that the one-minute open is derived from previous close.
- SuperMind documents historical minute/tick access and an auction callback in
  its hosted strategy environment, but that does not establish licensed raw
  export for this local NCN study. Its account, order, and simulation APIs are
  outside NCN's boundary.
- Wind advertises institution-oriented database and custom data services, but
  the public page inspected does not specify the required minute/auction
  schema, coverage, licence, or price. It requires a vendor quote before it can
  be compared.
- JoinQuant was region-blocked during this review, Ricequant documentation
  returned a transport error, and official exchange data-product pages tried
  in this session were unavailable. No capabilities were inferred from those
  failures.

## Fixed Acquisition Pilot

Do not buy or bulk-download first. After the user provides an appropriately
licensed credential, run one schema/coverage pilot with these fixed bounds:

- codes: `600000.SH`, `000001.SZ`, `600519.SH`, `000858.SZ`, and one historical
  risk-warning Main Board code selected without looking at SMC outcomes;
- dates: ten trading dates spread across 2021, 2023, and 2025, including one
  suspension/resumption date and one price-limit date where source coverage
  exists;
- endpoints: `stk_mins`, `stk_auction_o`, `stk_limit`, and `suspend_d` only;
- frequency/window: unadjusted `1min`, 09:30 through 09:35 inclusive;
- request budget: at most 100 API calls and 100 MB stored data;
- compute budget: one local process, under 15 minutes, no remote backtest.

The pilot passes only if all of these are verified:

- exchange/code/time-zone conventions and minute timestamp semantics are
  unambiguous;
- OHLC, volume, and amount are unadjusted and internally valid;
- opening-auction and 09:30 data reconcile under a documented provider rule;
- limit prices and suspension states are available for every tested date;
- zero-volume, missing-minute, locked-limit, and revised responses are
  distinguishable from ordinary trading;
- repeated identical requests are hash-stable, or revisions are explicitly
  versioned and excluded from point-in-time claims;
- the licence permits local retention and the intended private research use.

Any failed item stops acquisition. Do not replace missing fields with current
Eastmoney snapshots, adjusted `PFrontStockData`, inferred ST flags, or a second
vendor chosen after seeing outcomes.

## Frozen Reference-Observability Rule

The minute-bar dataset cannot evidence queue position or a user's actual order.
Accordingly the allowed state is named `reference_observable`, never `fill`.

For a tradable D, emit `reference_observable` only when all six 09:30-09:35
bars exist, total traded volume and amount are positive, the security is not
suspended, and the six-bar interval is not locked continuously at the daily
up-limit or down-limit. The descriptive reference price is the six-bar VWAP:

`sum(amount_09:30_09:35) / sum(volume_09:30_09:35)`

Emit `no_fill_evidence` for missing bars, zero volume/amount, suspension,
continuous limit lock, invalid prices, revision mismatch, or unavailable
status. `no_fill_evidence` is excluded from classifier fitting and reported as
its own coverage rate. It does not assert that an actual order would or would
not have filled.

This is one frozen reference rule. Do not compare D open, first-minute open,
first-minute close, six-minute VWAP, or alternate protection-limit variants by
outcome. If actual queue/fill evidence is later required, obtain order-level
market data and govern it in a separate execution-quality study outside NCN.

## Classifier Gate After Pilot

Do not implement or train a classifier during the acquisition pilot. If and
only if the pilot passes and licensed 2021-2025 coverage is sufficient, write a
separate preregistration that freezes one calibrated regularized-logistic
admission model before reading target outcomes. It must retain the periods,
features, comparators, purge/embargo rules, sample gates, precision/adverse
gates, coverage gate, and prospective requirement already fixed in the staged
solution document.

## Sources Reviewed

- Tushare historical A-share minutes: https://tushare.pro/document/2?doc_id=370
- Tushare opening-auction history: https://tushare.pro/document/2?doc_id=353
- Tushare daily price limits: https://tushare.pro/document/2?doc_id=183
- Tushare suspensions/resumptions: https://tushare.pro/document/2?doc_id=214
- Tushare permission and pricing table: https://tushare.pro/document/1?doc_id=290
- Tushare minute-data usage notes: https://tushare.pro/document/1?doc_id=234
- Tushare data service agreement: https://tushare.pro/document/1?doc_id=405
- SuperMind API documentation: https://quant.10jqka.com.cn/view/help/4
- Wind database service: https://www.wind.com.cn/portal/zh/WDS/database.html
