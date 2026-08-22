# NCN Edge Scout

Phased production-adjacent A-share research system with scanner, Web, demo portfolio, paper/simulation, PMKF/MKF analysis, AI review, risk controls, and audit workflows.

## Scope

- BaoStock incremental research-data update into `PFrontStockData/`;
- full-market and single-stock Edge Scout scans;
- CNstock-compatible discovery signals and daily research watchlist;
- approved-calendar/freshness-gated Research Production;
- integrated Web console with manually maintained research watchlist;
- demo portfolio and paper/simulation monitor with risk controls and append-only audit events;
- PMKF/MKF dashboards, candidate review, and centrally configured AI review;
- immutable publication, prospective evidence, replay, and maturity audits;
- macOS launchd scheduling, failure summaries, local alerts, and optional webhook.

The current phase permits research, demo portfolio, paper/simulation, PMKF/MKF dashboards, risk controls, audit logging, and operational hardening. It does not permit broker login, live order submission, leverage, unattended real-money execution, real account identifiers, or real-money P&L. BaoStock adjusted prices are research-only and must not be used as execution prices, fills, or return evidence.

Chinese operator documentation: [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) ([offline HTML](docs/USER_MANUAL.html)).

## Setup

```bash
./scripts/setup.sh
```

## Daily Scan

```bash
./scripts/edge_scout_scan.sh
```

The script checks BaoStock first. It skips download when local data is current with at least 95% latest-date coverage; otherwise it incrementally updates with `--no-clean` before scanning.

Offline local-data-only scan:

```bash
EDGE_SCOUT_AUTO_UPDATE=0 ./scripts/edge_scout_scan.sh
```

Main output:

```text
output/edge_scout/<run-id>/daily_research_watchlist.csv
```

All candidates are research-only. `production_enabled=false` is enforced fail-closed.

## Read-Only Stock Selection

Run the standalone SMC selector with existing local daily bars. This command
does not require minute data or a paid data service:

```bash
./main.sh select-local
./main.sh select-local --as-of 2026-08-11 --top 20
```

Use `./main.sh select` to check and incrementally update BaoStock daily research
data before selection. The selector keeps unchanged `smc_medium_buy` as its
primary signal, applies the configured Main Board/ST/listing/price/liquidity/
suspension/limit gates, and publishes every candidate under:

```text
output/edge_scout/selections/<run-id>/
```

`candidates.csv` and `candidates.json` contain the complete selected set;
`--top` limits terminal display only. Risk states are human-review warnings and
do not remove the primary candidate or issue buy/sell instructions.
Every run also writes a timestamped observation copy named
`smc_candidates_YYYYMMDD_HHMMSS.csv` in the same immutable run directory.
The saved `signal_date` is the completed T-1 session used by the signal. The
next trading session's T open is the intended entry reference for the later
`T_open * 1.03` target observation over T+1 through T+5. This first step does
not fetch T open, place an opening order, or track that target.

Run the experimental second review after a successful SMC selection:

```bash
./main.sh select-review [--as-of DATE] [--top 20]
./main.sh review-news --top 20  # --top limits terminal display only
```

It downloads recent Google News RSS titles and Eastmoney announcement metadata,
then sends filtered candidate-specific evidence, the existing SMC row, and local
daily K-line candlestick context through the signal date to the configured
OpenAI-compatible endpoint selected in `yaml/ai_providers.yaml`. The K-line context is a
read-only Japanese-candlestick-style OHLC/volume summary, not an execution feed.
All AI-backed features use this central file: edit its top-level `provider`, or add/update a
backend there, to switch MKF and SMC/news review together. Business configs such as
`yaml/news_ai_review.yaml` and `yaml/mkf_ai_review.yaml` cannot override provider/model settings.
Provider credentials are read from the configured environment variable first, then ignored key
files such as `Key/ts.key` and `Key/deepseek.key`; key contents are never copied into review output. Results are immutable under
`output/edge_scout/news_reviews/<run-id>/` and are bound to the source
`candidates.json` hash. `priority_review` is an experimental human-review order,
not a validated probability or buy instruction; API/news failures fail closed,
and code-level material-risk terms override favorable AI text.
News is cached per stock under ignored `.runtime/news_cache/`. A fresh cache is
reused without network access; refreshes merge and deduplicate new observations,
delete entries older than seven days, and send every remaining seven-day item
to the selected AI provider.
Every AI review writes `news_ai_reviews_YYYYMMDD_HHMMSS.csv` alongside its JSON
evidence. In the interactive menu, `SMC 选股（自动更新数据）` automatically runs
`SMC 新闻 AI 二次复核` after a successful selection; `SMC 新闻 AI 二次复核` remains
available as a separate manual action for reruns. Do not treat `ai_unavailable`
results as an AI-derived filter: they mean the configured provider could not
serve analysis.

## K-line Research Web

Open the latest published watchlist with local daily candles, HTTPS market snapshots, and
Eastmoney `1m/5m/15m/30m/60m` research candles:

```bash
./scripts/edge_scout_web.sh
```

Interactive control: run `./main.sh`, use the up/down arrow keys, and press Enter. The menu asks
for stock codes and optional dates when needed, so normal use does not require command arguments.
The menu includes `SMC 选股（自动更新数据）` and `SMC 选股（仅本地数据）`.
Pressing Enter on either starts selection immediately with the latest complete
daily data; the first option checks for BaoStock daily-data updates and then
runs the news AI review automatically after successful selection. Both run the
same selector whose historical T-open plus-3% target-touch rate was 59.74%;
that figure is a classification-only target-touch observation, not realized
profit, execution, fill, P&L, or a guarantee.

Direct commands remain available for automation:

```bash
./main.sh
./main.sh status
./main.sh restart

# Research scans:
./main.sh scan
./main.sh scan --as-of 2026-08-04
./main.sh scan-local
./main.sh select
./main.sh select-local --top 20
./main.sh select-review [--as-of DATE] [--top 20]
./main.sh review-news --top 20  # --top limits terminal display only
./main.sh single 600519
./main.sh single-local 600519
./main.sh update

# Equivalent lower-level control:
./scripts/edge_scout_web_control.sh
./scripts/edge_scout_web_control.sh status
./scripts/edge_scout_web_control.sh restart
```

Then visit `http://127.0.0.1:9091`. The Web console integrates read-only market research,
Demo Portfolio, Paper Monitor, PMKF/MKF reports, and audit/risk status. Demo and paper state are
simulation-only: there is no broker connection, live account, real-money P&L, or live order
submission. Override the bind address and port with `EDGE_SCOUT_WEB_HOST` and
`EDGE_SCOUT_WEB_PORT` when needed; keep the service on localhost unless access control is added.

Intraday responses display provider timestamps, adjustment metadata, freshness, source warnings,
and whether the latest candle is still forming. External-provider failure is shown explicitly and
never silently replaced with daily data. The Sina and Eastmoney public endpoints have no exchange
latency SLA and must not be treated as execution feeds.

While the page is visible, snapshots and intraday candles are scheduled for refresh every 15
seconds; daily candles refresh every 60 seconds. Background tabs pause network polling and refresh
immediately when visible again. Provider latency and bounded retries can make completion later than
the scheduled interval, which is shown by the on-page refresh status.

The left rail is a manually maintained research watchlist stored atomically in
`config/research_watchlist.json` (ignored by Git). Only selected securities appear in the monitor.
It stores codes only, never cost, quantity, cash, transactions or returns. Indicator reminders use
transparent research states: bullish setup confirmed, setup waiting for confirmation, trend watch,
and structural risk observation. These are prompts for manual review, not personalized buy/sell
instructions or order triggers.

## Scheduler

Create `.env.edge_scout_schedule` from `config/edge_scout_schedule.env.example`, then install:

```bash
./scripts/install_edge_scout_launchd.sh
```

The NCN LaunchAgent identity is `com.vartw.stock-ncn.edge-scout`, scheduled Monday-Friday at 18:30.

## Tests

```bash
.venv/bin/python -m pytest -q
```
