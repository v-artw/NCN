# NCN Standalone Acceptance

Date: 2026-08-03

## Boundary

NCN contains only the Edge Scout research scanner, local pure-function support modules, BaoStock downloader, approved-calendar evidence, scheduler, configuration, and related tests.

Explicitly excluded:

- `a_share_short_swing` package;
- portfolio, execution, orders, ledger, backtest, and simulation modules;
- broker connectivity and live trading;
- runtime paths into `Stock/CN` or `CNstock`.

## Independent Resources

```text
project: /Users/artx/Local/Git/Stock/NCN
python:  /Users/artx/Local/Git/Stock/NCN/.venv/bin/python
data:    /Users/artx/Local/Git/Stock/NCN/PFrontStockData
output:  /Users/artx/Local/Git/Stock/NCN/output
agent:   com.vartw.stock-ncn.edge-scout
```

The 7329 parquet files are an independent APFS clone, not a symbolic link. Deleting the source project does not invalidate the NCN paths.

## Acceptance Evidence

- isolated package import: passed; no `a_share_short_swing` module loaded;
- real BaoStock check: local and remote latest `2026-08-03`, coverage 99.81%;
- full-market scan `market-20260803_225819`: success, 7329 input, 830 scored, 0 unexpected errors;
- explicit external-data integration suite: 20 passed;
- scheduled production `scheduled-20260803_231258`: success, lag 0, coverage 99.81%;
- default standalone suite: 100 passed, 3 expected external-data skips;
- launchd plist, shell syntax, and Python compilation: passed.

Calendar approval remains restricted to read-only Research Production and does not authorize execution, return calculation, paper trading, or live trading.
