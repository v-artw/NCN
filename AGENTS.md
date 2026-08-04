# NCN Agent Instructions

## Boundaries

- NCN is a standalone, read-only A-share research scanner. Do not add broker login, orders, leverage, paper trading, backtesting, return calculation, or live trading.
- `PFrontStockData/` contains adjusted research data only; never use it as execution, matching, or return input.
- Keep `production_enabled: false` in `yaml/edge_scout_v1.yaml`. Calendar approval authorizes read-only Research Production only.
- Keep runtime imports within `ashare_edge_scout` or declared third-party dependencies. Do not add dependencies on `Stock/CN`, `CNstock`, or `a_share_short_swing`.
- The manual Web list is a research watchlist, not a portfolio. Store codes only; do not add cost, quantity, cash, transactions, P&L, or personalized buy/sell instructions. Indicator states are prompts for human review.

## Package And Data Flow

- This is a single `src`-layout Python package (`ashare_edge_scout`); package discovery and pytest's `src` path are configured in `pyproject.toml`.
- Scans read validated per-code Parquet from `PFrontStockData/` and atomically publish immutable runs under `output/edge_scout/<run-id>/`; `output/edge_scout/latest.json` points the Web UI at the latest successful run.
- `src/ashare_edge_scout/research_web.py` is the Web/API entrypoint. It combines published scan rows, local daily bars, and the native HTTPS adapters in `intraday_data.py`; it must not import legacy projects.
- Keep the Web server on the stdlib serial `HTTPServer`. Concurrent PyArrow reads under Python 3.14 caused native crashes; local UI throughput does not justify switching back to a threaded server.
- Sina snapshots and Eastmoney `1m/5m/15m/30m/60m` bars have no exchange latency SLA. Preserve provider/source timestamps, freshness, forming-bar state, warnings, bounded retry/cache behavior, and explicit last-observation fallback; never present them as execution feeds.
- `config/research_watchlist.json` is an ignored, atomically written local file containing codes only. `.runtime/` is ignored process state/logging for the managed Web service.

## Commands

- Set up the supported environment with `./scripts/setup.sh`; it creates `.venv` and installs the package plus pytest. Supported Python is `>=3.12,<3.15`.
- Run the default suite with `.venv/bin/python -m pytest -q`. For a focused test, pass a file or node id, for example `.venv/bin/python -m pytest tests/test_edge_scout_config.py -q`.
- `./main.sh` without arguments is a TTY-only arrow-key menu. For automation use `./main.sh start|stop|restart|status`, `scan [--as-of DATE]`, `scan-local`, `single <code> [--as-of DATE]`, `single-local <code>`, or `update`.
- `./scripts/edge_scout_scan.sh` is the underlying scanner wrapper and supplies `PYTHONPATH=src` plus `.venv`. It checks BaoStock freshness and incrementally updates with `--no-clean` by default; set `EDGE_SCOUT_AUTO_UPDATE=0` for deterministic local-data-only work.
- Manage the background Web only through `./scripts/edge_scout_web_control.sh start|stop|restart|status` (or `main.sh`); it owns `.runtime/edge_scout_web.pid`, logs, PID validation, and HTTP health checks. `edge_scout_web.sh` is the foreground entrypoint.
- Use `./scripts/edge_scout_production.sh` for the calendar/freshness-gated production wrapper. It fails closed unless the approved calendar path, SHA-256, coverage, freshness, and atomic publication checks pass.
- After Web changes, at minimum run the focused Python test, `node --check src/ashare_edge_scout/web_static/app.js`, and `git diff --check`. Playwright is intentionally separate in ignored `.venv-playwright`; the default setup/test suite does not install or require it.

## Scheduling

- Scheduled runs require a reviewed `.env.edge_scout_schedule` copied from `config/edge_scout_schedule.env.example`; it must provide `EDGE_SCOUT_CALENDAR`, `EDGE_SCOUT_CALENDAR_SHA256`, and `EDGE_SCOUT_CALENDAR_APPROVAL`.
- The macOS LaunchAgent is `com.vartw.stock-ncn.edge-scout`, installed with `./scripts/install_edge_scout_launchd.sh`; it runs weekdays at 18:30 in the logged-in user session.
