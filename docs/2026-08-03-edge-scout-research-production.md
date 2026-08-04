# Edge Scout Research Production

This document defines the first productionization stage for the read-only Edge Scout service. It does not enable paper trading, broker connectivity, order submission, or investment advice.

## Entry Point

Use the noninteractive wrapper. Without calendar overrides, it uses the approved BaoStock 2026 read-only research calendar committed in this project:

```bash
./scripts/edge_scout_production.sh
```

The calendar is a newline-delimited list of exchange trading dates. `EDGE_SCOUT_CALENDAR` and `EDGE_SCOUT_CALENDAR_SHA256` may override the approved defaults. The repository file `config/trading_calendar_2026.txt` is an unapproved research-data date list and must not be used as production-calendar evidence.

The wrapper supports these environment variables:

| Variable | Meaning |
|---|---|
| `EDGE_SCOUT_DATA_ROOT` | research data root |
| `EDGE_SCOUT_CONFIG` | Edge Scout configuration |
| `EDGE_SCOUT_OUTPUT_ROOT` | result and operations root |
| `EDGE_SCOUT_CALENDAR` | reviewed explicit trading calendar; defaults to the approved repository candidate |
| `EDGE_SCOUT_CALENDAR_SHA256` | approved calendar content digest; defaults to the matching approved digest |
| `EDGE_SCOUT_RUN_ID` | immutable run identifier |
| `VENV_PYTHON` | Python interpreter override |

## Gates

The production entry point fails closed unless:

- the calendar is valid, strictly increasing, and matches the approved SHA-256;
- observed data is not from the future;
- latest observed data is within the configured trading-day lag;
- `as_of` is exactly two calendar trading days before the observed latest date;
- latest-date coverage meets the configured minimum of 95%;
- the scan completes with `status=success`;
- the result bundle is atomically published before `latest.json` changes.

The default production freshness lag is zero trading days. The default output keeps 30 validated run bundles. Retention never deletes the run referenced by `latest.json` or operational directories.

## Operations

Each run uses `output-root/.edge_scout_production.lock/`. The lock contains owner metadata and fails closed if another run holds it. Operational logs and an atomic `operations_summary.json` are written under:

```text
output-root/operations/<run-id>/
```

`latest.json` continues to mean the last completely successful publication. A failed attempt is recorded in its operations directory and never replaces a previous successful `latest.json`.

## Approved Calendar And Scheduling

The workspace owner approved the BaoStock 2026 candidate for **read-only research production only**. The approval is bound to:

```text
calendar: config/review_candidates/baostock_calendar_2026_candidate.txt
sha256:   fd77a04f5268efd4803ca99877a0de4b126a51ad01a45b24c443afc8f8aa3ee7
approval: config/review_candidates/baostock_calendar_2026_approval.json
```

This approval does not cover execution prices, return calculation, paper trading, or live trading. Scheduled runs validate the approval scope, path, and digest before any update or scan.

The standalone NCN LaunchAgent is `com.vartw.stock-ncn.edge-scout`, scheduled Monday through Friday at 18:30. It runs `scripts/run_edge_scout_scheduled.sh`, which performs the conditional BaoStock update and then the calendar/freshness-gated research-production scan. It keeps 30 timestamped logs and summaries, enforces a two-hour timeout, posts a local macOS notification on failure, and optionally sends a JSON webhook when `EDGE_SCOUT_ALERT_WEBHOOK_URL` is configured in `.env.edge_scout_schedule`.

Operational commands:

```bash
launchctl print gui/$(id -u)/com.vartw.stock-ncn.edge-scout
launchctl kickstart -k gui/$(id -u)/com.vartw.stock-ncn.edge-scout
launchctl bootout gui/$(id -u)/com.vartw.stock-ncn.edge-scout
```

The LaunchAgent requires the user session and workstation to remain available; it is not a server-grade high-availability scheduler.

## Not Yet Production

This stage does not prove PIT historical universe completeness, raw execution price authenticity, corporate-action handling, ledger correctness, paper simulation, or profitability. `PFrontStockData/` remains research-only adjusted data.
