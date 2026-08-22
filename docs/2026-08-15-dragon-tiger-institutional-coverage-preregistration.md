# Dragon-Tiger Institutional Coverage Preregistration

## Frozen Hypothesis And Source Fact

One hypothesis is permitted: an A-share Dragon-Tiger event whose official SSE
or SZSE detail names at least one seat exactly `机构专用` and whose deduplicated
disclosed institutional buy amount minus disclosed institutional sell amount is
strictly positive may improve the precision of the existing five-tradable-day
classification task. `沪股通专用`, `深股通专用`, named broker branches, inferred
institutions, Eastmoney classifications, and Eastmoney aggregates are excluded.

This document freezes a source-coverage probe, not a strategy evaluation. No
future price, return, or label may be read unless this probe passes and a
separate Stage 1 preregistration is committed first.

## Reviewed Contracts And Permitted Fields

- SSE official list: `query.sse.com.cn/marketdata/tradedata/queryAllTradeOpenDate.do`.
  SSE official detail: `query.sse.com.cn/marketdata/tradedata/queryTradeOpenInfo.do`.
- SZSE official list: `www.szse.cn/api/report/ShowReport/data`, catalog
  `1842_xxpl`. SZSE official detail: the same path, catalog `1842_detal`.
- Retain only exchange, event date, code, exchange reason/reference type, exact
  seat name, buy amount, sell amount, raw-response SHA-256, source URL/parameters,
  and retrieval time. No price, price change, turnover, market value, adjusted
  change, interpretation, ranking, or future-performance field is retained.
- AKShare commit `1248fdd05a2dda92937d4cd39c0957825f2f7f6e`
  was reviewed only as adapter evidence. `stock_lhb_jgmmtj_em` uses Eastmoney
  `RPT_ORGANIZATION_TRADE_DETAILS`; `stock_lhb_detail_em` explicitly requests
  `D1/D2/D5/D10_CLOSE_ADJCHRATE`. Neither Eastmoney response is an accepted
  cache source for this study.
- Exchange seat names and disclosed buy/sell amounts are daily event facts.
  They are treated as historical point-in-time facts at the conservative
  availability below, not as proof of an institution's ultimate beneficial
  identity or complete trading activity outside the published top-seat table.

## Fixed Availability And Deduplication

- The exchange contracts expose a trading/publication date but no defensible
  intraday publication timestamp. Every retained event is first available on
  that stock's next tradable date after the exchange event date.
- The event key is `(exchange, event_date, code, reason_reference)`; different
  Dragon-Tiger reasons on one code/date remain separate events.
- A SZSE detail can repeat one seat with identical buy and sell amounts in its
  buy and sell ranking. Deduplicate exact `(seat_name, buy_amount, sell_amount)`
  tuples within an event before summing. SSE buy and sell rows are summed by the
  exchange-provided side. No fuzzy name matching or cross-reason netting occurs.
- Amounts must be finite, nonnegative, and explicitly present. Zero is valid.
  Missing/conflicting values invalidate the event rather than being inferred.

## Fixed Coverage Universe

Use the immutable code list in `docs/research/results/stage1/precision70-stage1-2021-2026.json`. The probe is
exactly the first 20 `sh.` codes and first 20 `sz.` codes in that stored order:

- SSE: `600000`, `600021`, `600025`, `600031`, `600052`, `600055`, `600085`,
  `600096`, `600100`, `600105`, `600132`, `600148`, `600161`, `600162`,
  `600166`, `600169`, `600176`, `600192`, `600196`, `600216`.
- SZSE: `000016`, `000020`, `000032`, `000045`, `000061`, `000089`, `000156`,
  `000166`, `000401`, `000429`, `000505`, `000514`, `000519`, `000531`,
  `000532`, `000534`, `000536`, `000539`, `000557`, `000564`.

Query every official list row from 2021-01-01 through 2026-08-15 for these
codes, complete every page, then request every corresponding official detail.
The probe is exchange-balanced because a lexicographic first-40 slice would
contain only SSE codes and would not test the SZSE contract.

## Frozen Coverage Gates

All gates must pass:

- Every list query/page and every referenced detail succeeds, validates, and
  has no unexplained pagination mismatch; normalized repeated-query hashes are
  equal for one fixed nonempty list and detail on each exchange.
- At least 95% of discovered reason-events have a valid date, code, reason,
  complete detail, and valid explicit seat amounts. No selected event may have
  an invalid required field.
- Positive exact-`机构专用` net events appear in every full year 2021-2025 and
  in partial 2026; at least five appear in each of 2023, 2024, and 2025, and at
  least three in 2026.
- There are at least 30 positive events in selection 2023-2024 and at least 30
  in holdout 2025-2026. The probe is 10% of the fixed Stage 1 codes, so these
  are the minimum proportional counts compatible with the existing `n>=300`
  selection and holdout gates; passing does not guarantee full-sample counts.
- At least 16/40 codes and at least 8/20 codes on each exchange have one valid
  official Dragon-Tiger detail. At least 8/40 codes have a positive exact
  institutional-net event, preventing concentration in one or two names.

## Budget And Stop Rule

- Maximum 1,200 HTTP requests including retries and repeated checks, 250 MB raw
  response bytes, one worker, two retries per request, and 15 seconds per try.
- Archive raw responses, request parameters, retrieval timestamps, and SHA-256
  hashes under ignored `.runtime/`; write only a compact audit report outside
  the archive if the probe passes.
- If any gate fails, exceeds budget, or either official contract cannot be
  retrieved defensibly, stop this direction. Do not substitute Eastmoney or
  Sina, broaden seat identity, merge reasons, change the sample/counts, inspect
  price labels, create a Stage 1 preregistration, or run a backtest.
- Only a complete coverage pass permits implementation of a leakage-safe event
  cache and focused tests, followed by a separate frozen Stage 1 document. That
  later Stage 1 must preserve the existing 70% precision, minimum-count,
  annual-coverage, Wilson-lower-bound, and non-overlap gates and may run once in
  WSL, then Doris, then local fallback order.

## Terms Boundary

SSE and SZSE legal statements permit browsing/downloading website content for
noncommercial purposes while reserving intellectual-property rights and
prohibiting unlicensed resale or profit-oriented redistribution. This bounded,
local, read-only research archive is not redistributed. AKShare's MIT license
covers its adapter code, not exchange data rights.
