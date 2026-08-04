# NCN Edge Scout

Standalone A-share read-only research scanner extracted from `Stock/CN`.

## Scope

- BaoStock incremental research-data update into `PFrontStockData/`;
- full-market and single-stock Edge Scout scans;
- CNstock-compatible discovery signals and daily research watchlist;
- approved-calendar/freshness-gated Research Production;
- macOS launchd scheduling, failure summaries, local alerts, and optional webhook.

This project does not contain portfolio, execution, orders, backtesting, paper trading, broker connectivity, or live trading code. BaoStock adjusted prices are research-only and must not be used as execution prices or return evidence.

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

## K-line Research Web

Open the latest published watchlist with local daily candles, HTTPS market snapshots, and
Eastmoney `1m/5m/15m/30m/60m` research candles:

```bash
./scripts/edge_scout_web.sh
```

Interactive control: run `./main.sh`, use the up/down arrow keys, and press Enter. The menu asks
for stock codes and optional dates when needed, so normal use does not require command arguments.

Direct commands remain available for automation:

```bash
./main.sh
./main.sh status
./main.sh restart

# Research scans:
./main.sh scan
./main.sh scan --as-of 2026-08-04
./main.sh scan-local
./main.sh single 600519
./main.sh single-local 600519
./main.sh update

# Equivalent lower-level control:
./scripts/edge_scout_web_control.sh
./scripts/edge_scout_web_control.sh status
./scripts/edge_scout_web_control.sh restart
```

Then visit `http://127.0.0.1:9091`. The web console is read-only. It does not expose portfolio,
returns, backtesting, execution, or order operations. Override the bind address and port with
`EDGE_SCOUT_WEB_HOST` and `EDGE_SCOUT_WEB_PORT` when needed.

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
