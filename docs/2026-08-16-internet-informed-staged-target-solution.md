# Internet-Informed Staged-Target Research Solution

## Decision

Do not search another fixed stop percentage on adjusted daily bars. Preserve
`smc_medium_buy` as the sole primary signal and test one secondary admission
layer whose label exactly matches the user's intended D-open, A-share T+1,
3%-to-5%, maximum-five-day workflow. NCN remains read-only and does not place or
simulate broker orders, positions, allocation, returns, or P&L.

## Why This Direction

- The completed full-universe path study found that SMC Medium produces both
  larger favorable and adverse excursions. Fixed +3/-3 and +5/-5 barriers did
  not yield a stable favorable path advantage.
- SSE states that Main Board orders are matched by price priority and time
  priority, and distinguishes limit and market orders; an observed D open is not
  proof that a user limit order filled there. Main Board A shares generally have
  10% daily limits and risk-warning shares 5% limits.
- SZSE likewise documents auction price/time priority, price limits, and trading
  hours. Its overview is an official rules entry point; the currently accessible
  English turn-around summary is not sufficient by itself to restate a precise
  Main Board A-share T+1 clause, so the implementation must bind to reviewed
  current Chinese rules before any external execution study.
- Lopez de Prado's published-method summary identifies triple-barrier labels as
  congruent with profit-taking, stop-loss, and horizon; meta-labeling as a way to
  filter a primary signal for higher precision; and purging/embargo as controls
  for overlapping-label leakage.
- Bailey et al. document probability of backtest overfitting, and Lopez de
  Prado's summary identifies PBO, minimum backtest length, and deflated Sharpe
  as safeguards against selecting the best of many trials. The current project
  has already inspected many OHLCV variants, so another parameter grid is not
  admissible evidence.

## Frozen Candidate Study

### Primary Signal

- Only unchanged `smc_medium_buy`.
- `smc_bull_bos` and `kdj_trend_pro_buy` remain descriptive comparators, not
  fallback candidates.

### Entry Observation

- Signal at T close using T-visible data only.
- External execution-quality dataset must contain unadjusted point-in-time
  opening-auction/one-minute data, security status, price limits, and volume.
- Reference fill rule is frozen before data access. Recommended research rule:
  first executable price from 09:30-09:35 subject to a predeclared protection
  limit and minimum displayed/traded liquidity. Unfilled observations are
  `no_fill`, never silently filled at D open.
- NCN may display source/freshness and research reference prices, but cannot
  claim a fill or connect to a broker.

### Outcome And Horizon

- A-share T+1: no eligible exit on D. Observe D+1 onward.
- Primary horizon: D+1 through D+5. Reject D+6 through D+10 as default because
  the completed full-universe study found more newly risk-first than
  target-first events among five-day unresolved observations.
- Fixed target versions only: A = all at +3%; B = equal descriptive sublabels at
  +3% and +5%. Do not add +4%, +6%, trailing, or grid variants.
- Triple-barrier path states remain target-first, adverse-first,
  same-bar-ambiguous, time-expired, no-fill, suspended/locked, and invalid-data.
  Ambiguous and locked states cannot be counted as successful.

### Secondary Admission Layer

- Predict only whether the unchanged primary SMC signal is path-suitable; do
  not predict every stock or replace the primary rule.
- Fixed causal feature families available before/at the research entry cutoff:
  T trend structure, T ATR/realized volatility, T liquidity, D opening gap,
  broad-market regime, sector breadth when point-in-time provenance exists, and
  opening-auction/first-five-minute volume-price quality when licensed data is
  available.
- Exclude Japanese candle votes, duplicate oscillators, news/AI sentiment,
  future-adjusted values, and any feature without point-in-time provenance.
- Prefer an interpretable regularized logistic classifier or a small monotonic
  tree model. Probability must be calibrated. The model is an admission filter,
  not a return forecast or trade instruction.

## Validation Contract

- Global date splits, never per-stock block splits.
- Purge every training origin whose five-day outcome overlaps validation; apply
  an embargo after validation boundaries.
- Fixed periods: 2021-2023 development/selection, 2024-2025 untouched audit,
  2026 prospective-only observation. Do not inspect prospective outcomes while
  changing the model.
- Comparator: unchanged all-SMC same-date cohort and same-date admitted market.
- Minimum gates in both selection and audit: n>=300, >=120 signal dates, >=50
  codes, target-first precision lift >=3 percentage points over parent SMC,
  Wilson lower bound above parent precision, adverse-first rate no higher than
  parent, positive annual lifts, calibrated Brier improvement, and at least 25%
  retained SMC coverage.
- Record the number of attempted specifications. Estimate PBO or use an
  equivalent multiple-testing audit; reject if results depend on choosing among
  many variants. A failed frozen candidate stops the direction.
- Promotion remains prospective-only. Require unchanged prospective sufficiency
  before adding even a research-stage warning to the scanner.

## Daily Read-Only Product

- Night: publish unchanged SMC research candidates and reasons.
- Morning: display opening reference, gap, liquidity/freshness warnings, model
  admission probability/state, +3%/+5% research levels, and `no_fill` when the
  frozen execution-quality rule is not observable.
- Following days: archive D+1..D+5 path states and maturity. No holdings, cost,
  quantity, cash, transaction, P&L, broker login, order, or personalized action.

## Sources

- SSE Trading Mechanism: https://english.sse.com.cn/start/trading/mechanism/
- SZSE Trading Overview: https://www.szse.cn/English/services/trading/tradOverview/index.html
- SSE current rule directory: https://www.sse.com.cn/lawandrules/sselawsrules/trade/universal/
- SSE fees (January 2026): https://www.sse.com.cn/services/tradingservice/charge/ssecharge/
- Lopez de Prado published innovations summary: https://www.quantresearch.org/Innovations.htm
- Bailey et al., *The Probability of Backtest Overfitting*: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

Several historical SSE/SZSE/CSRC deep links and SSRN delivery URLs returned
404/403/transport errors during this review. They were not used to assert exact
clauses or numerical claims.
