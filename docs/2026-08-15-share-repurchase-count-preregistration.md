# Quantified Share-Repurchase Proposal Count Preregistration

## Frozen Hypothesis And Phase Boundary

One independent hypothesis is permitted: an initial A-share issuer share-
repurchase proposal whose original official announcement conservatively discloses
a positive minimum committed amount or share count, funding source, and purpose
may improve the existing five-tradable-day classification precision. This is a
metadata-only upper-bound count probe. No PDF and no price, return, outcome, or
future label may be read unless every gate below passes. A passing count probe
permits only a separate PDF source probe; a passing PDF source probe then permits
only a separately written Stage 1 preregistration.

## Reviewed Evidence And Source Contracts

- Official metadata source: CNInfo historical announcements,
  `https://www.cninfo.com.cn/new/hisAnnouncement/query`, with immutable
  `announcementId`, issuer code and organization ID, title,
  `announcementTime`, and `adjunctUrl`. Linked original documents are under
  `https://static.cninfo.com.cn/` but are forbidden in this phase.
- AKShare commit `1248fdd05a2dda92937d4cd39c0957825f2f7f6e` was
  reviewed as adapter evidence. `stock_zh_a_disclosure_report_cninfo` uses the
  official CNInfo contract and complete 30-row pagination. `stock_repurchase_em`
  instead uses Eastmoney `RPTA_WEB_GETHGLIST_NEW`, combines stages 001 through
  006, and exposes latest/progress fields; it is not an immutable initial-event
  source and is excluded.
- SSE and SZSE repurchase rules require prompt disclosure of a proposal or board
  resolution and distinguish the repurchase report, implementation progress,
  completion, and changes/termination. CNInfo is the common official disclosure
  archive used for the count; direct exchange pages remain corroborating
  contracts, not substitute records. Official contract entry points reviewed:
  `https://www.sse.com.cn/disclosure/listedinfo/announcement/`,
  `https://www.sse.com.cn/lawandrules/sselawsrules/stocks/mainipo/`, and
  `https://www.szse.cn/lawrules/rule/stock/supervision/currency/index.html`.
- Peer-reviewed evidence is directional, not a 70% claim. Gan, Bian, Wu and
  Cohen (2017), `https://doi.org/10.21511/imfi.14(2).2017.01`, studies Chinese
  repurchase-announcement returns; Zhang (2019),
  `https://doi.org/10.1080/13504851.2019.1676380`, reports that China's Company
  Law revision changed market reactions. Neither establishes NCN's label,
  short horizon, PIT completeness, or required precision.

## Fixed Universe, Availability, And Identity

- Use exactly the 400 `sample.code_list` entries already frozen in
  `docs/research/results/stage1/precision70-stage1-2021-2026.json`, preserving stored order. Reading is
  limited programmatically to that list; result summaries and future labels in
  the artifact are not research inputs.
- Query 2021-01-01 through 2026-08-15 for search key `回购`, one code at a time,
  and complete every 30-row page. Deduplicate only by nonempty immutable
  `announcementId`; conflicting fields for one ID invalidate the probe.
- Retain only announcement ID, code, organization ID, exact normalized title,
  provider timestamp, PDF URL (not fetched), request parameters, retrieval time,
  response SHA-256, and response bytes.
- CNInfo metadata does not provide a defensible exchange-session cutoff.
  Therefore every candidate would first be usable on the stock's next tradable
  date strictly after the provider timestamp's Shanghai calendar date. No local
  trading calendar or stock bars may be opened during this count probe.
- The event is the earliest accepted initial announcement ID per code and
  normalized proposal subject. Multiple documents on one code/date count only
  when their normalized titles identify distinct repurchase proposals; generic
  duplicate initial titles count once per code/date.

## Frozen Exact Title Rules

Normalize by removing CNInfo highlight HTML, issuer prefixes such as `公司关于`,
all whitespace, and full-width/ASCII punctuation; preserve all Chinese words.
The title must contain `回购` and `股份` or `股票`.

An upper-bound initial candidate must contain at least one of these exact title
phrases:

- `回购股份方案`, `回购公司股份方案`, or `股份回购方案`;
- `回购股份预案`, `回购公司股份预案`, or `股份回购预案`;
- `回购股份提议`, `提议回购股份`, `提议公司回购股份`, or
  `关于提议回购公司股份`;
- `董事会审议通过回购股份`, `董事会审议通过回购公司股份`, or a
  `董事会决议公告` title that also contains `回购股份方案` or `回购公司股份方案`.

The candidate is rejected from the initial count if the title contains any of:

- progress/implementation: `进展`, `实施进展`, `首次回购`, `首次实施`,
  `实施回购`, `回购报告书`, `回购股份报告书`, `回购结果`, `实施结果`;
- completion/expiry: `完成`, `实施完成`, `回购完成`, `期限届满`, `届满`;
- cancellation/termination/change: `终止`, `停止`, `取消`, `撤回`, `变更`,
  `调整`, `注销`, `出售`;
- correction/supplement/reminder: `更正`, `补充`, `修订`, `更新`, `提示性`,
  `延期`, `延长`;
- later approval or mechanics: `股东大会决议`, `债权人通知`, `通知债权人`,
  `回购专用证券账户`, `回购专户`, `集中竞价交易方式回购进展`.

All matched and excluded records are separately counted by frozen state. Titles
that merely mention another party's repurchase, employee plans, equity
incentives, convertible bonds, or fund units without an issuer-share proposal
are excluded as `other`.

## Frozen Count And Completeness Gates

Every gate must pass before any PDF retrieval:

- Every code exists in the official stock map; every query/page succeeds and
  exactly matches `totalAnnouncement`; all retained IDs, codes, organization
  IDs, timestamps, titles, and PDF links validate; repeated complete retrieval
  has the same normalized metadata hash.
- At least 95% of all exact-title initial candidates have complete required
  metadata, with no conflicting duplicate announcement ID.
- Initial candidates appear in every year 2021 through 2025 and partial 2026.
- Selection 2023-2024 has at least 300 distinct initial events, including at
  least 50 in 2023 and 50 in 2024.
- Holdout 2025-2026 has at least 300 distinct initial events, including at least
  50 in 2025 and 25 in partial 2026.
- At least 120/400 codes have an initial event. Counts are only a feasibility
  upper bound; they provide no evidence of 70% precision or a 60% Wilson lower
  bound. Stage 1 would retain the existing precision, Wilson, annual,
  non-overlap, and sample gates unchanged.

## Budget And Stop Rule

- Maximum 1,800 HTTP requests including retries and repeat retrieval, 100 MB of
  metadata response bytes, one worker, two retries, 15 seconds per attempt, and
  30 minutes wall time. Maximum PDF requests and PDF bytes are both zero.
- Archive raw metadata, request parameters, timestamps, and SHA-256 hashes only
  under ignored `.runtime/share-repurchase-count-probe/`.
- If any gate fails or the budget is exceeded, stop this direction before PDF
  parsing, price labels, Stage 1 preregistration, or remote evaluation. Do not
  broaden titles, count progress/completion/correction records, substitute
  Eastmoney, alter the sample, lower counts, or reinterpret one proposal's
  repeated announcements as independent events.
- Only a full count pass permits a frozen PDF source probe. That probe must
  conservatively parse an explicit positive minimum amount or shares, funding,
  and purpose from original PDFs, with its own request/PDF/completeness gates.

## Frozen Probe Result

The live probe stopped during pass 1 at code `603551`, before counts could be
completed. CNInfo pages 1, 2, and 3 each declared `totalAnnouncement=96` and
returned 30 rows; page 4 declared `totalAnnouncement=94` and returned 4 rows.
This violates the frozen stable-total/complete-pagination source gate. The probe
made 201 metadata requests, archived 2,406,044 response bytes, and made zero PDF
requests. No price or future-label source was opened. Decision: stop before PDF
parsing and labels; incomplete partial counts are intentionally not reported or
used to reconsider the gate.
