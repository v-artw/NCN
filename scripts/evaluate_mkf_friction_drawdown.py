#!/usr/bin/env python3
"""Friction + per-position drawdown study on the MKF post-cross target grid.

Reuses the validated target-grid panel builder and adds realistic A-share trading
frictions (fixed 3-lot / 300-share position) and per-position drawdown, ranked by
net return minus average single-position drawdown. Descriptive in-sample research
only; no production selector, watchlist, AI, or broker path is touched.

Run on a small sample first to time the per-stock cost, then full-run:

    env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=src \
      .venv/bin/python scripts/evaluate_mkf_friction_drawdown.py \
      --data-root PFrontStockData \
      --config yaml/edge_scout_v1.yaml \
      --start-date 2021-01-01 \
      --file-limit 50 \
      --output .runtime/mkf-friction-drawdown.json \
      --summary-csv .runtime/mkf-friction-drawdown.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.pmkf_mkf.mkf_friction_drawdown import (
    STUDY_HORIZONS,
    STUDY_TARGET_PCTS,
    build_report,
    compute_stock_friction_drawdown,
)
from ashare_edge_scout.research_precision70 import PREFIXES

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--file-limit", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, default=None)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    return args


def _stock(path: Path, config: Mapping[str, Any], start_date: str, end_date: str | None) -> dict[str, Any]:
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return compute_stock_friction_drawdown(
        path.stem,
        frame,
        config,
        start_date=start_date,
        end_date=end_date,
    )


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    paths = sorted(
        path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)
    )
    if args.file_limit is not None:
        paths = paths[: args.file_limit]
    if not paths:
        raise SystemExit("no current main-board Parquet files found")
    config = load_config(args.config)

    cell_sums: dict[tuple[int, int, int], dict[str, Any]] = {}
    codes: dict[tuple[int, int], int] = {}
    entry_dates: dict[tuple[int, int], set] = {}
    code_list: list[str] = []

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, per_stock in enumerate(executor.map(_stock, paths, [config] * len(paths), [args.start_date] * len(paths), [args.end_date] * len(paths)), start=1):
            code_list.append(paths[index - 1].stem)
            for cell, partial in per_stock["cells"].items():
                acc = cell_sums.get(cell)
                if acc is None:
                    cell_sums[cell] = dict(partial)
                else:
                    acc["n"] += partial["n"]
                    acc["hits"] += partial["hits"]
                    acc["sum_net_return"] += partial["sum_net_return"]
                    acc["sum_net_return_sq"] += partial["sum_net_return_sq"]
                    acc["sum_drawdown"] += partial["sum_drawdown"]
                    acc["sum_drawdown_sq"] += partial["sum_drawdown_sq"]
                    acc["max_drawdown"] = max(acc["max_drawdown"], partial["max_drawdown"])
            for (lag, horizon), count in per_stock["codes"].items():
                codes[(lag, horizon)] = codes.get((lag, horizon), 0) + count
            for (lag, horizon), dates in per_stock["entry_dates"].items():
                entry_dates.setdefault((lag, horizon), set()).update(dates)
            if index % 200 == 0 or index == len(paths):
                print(f"processed {index}/{len(paths)} files", flush=True)

    code_list.sort()
    report = build_report(
        cell_sums,
        codes=codes,
        entry_dates=entry_dates,
        code_list_sha256=hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest(),
        start_date=args.start_date,
        end_date=args.end_date,
        workers=args.workers,
        horizon_limits=STUDY_HORIZONS,
        lags=tuple(range(0, 8)),
    )
    report["sample_codes"] = len(code_list)
    _atomic_json(args.output, report)
    if args.summary_csv is not None:
        _atomic_csv(args.summary_csv, [
            {
                "lag": row["lag"],
                "horizon": f"T+{row['horizon']}",
                "target_pct": row["target_pct"],
                "n": row["n"],
                "hit_rate": row["hit_rate"],
                "mean_net_return": row["mean_net_return"],
                "mean_drawdown": row["mean_drawdown"],
                "max_drawdown": row["max_drawdown"],
                "score": row["score"],
            }
            for row in report["scored"]
        ])
    best = report["best_cell"]
    best_by_net = report["best_by_net_return"]
    best_by_dd = report["best_by_drawdown"]
    print(
        f"best_cell (net-dd 1:1) lag={best.get('lag')} horizon=T+{best.get('horizon')} "
        f"target={best.get('target_pct')}% score={best.get('score')} net={best.get('mean_net_return')} dd={best.get('mean_drawdown')}",
        flush=True,
    )
    print(
        f"best_by_net_return lag={best_by_net.get('lag')} horizon=T+{best_by_net.get('horizon')} "
        f"target={best_by_net.get('target_pct')}% net={best_by_net.get('mean_net_return')} dd={best_by_net.get('mean_drawdown')}",
        flush=True,
    )
    print(
        f"best_by_drawdown lag={best_by_dd.get('lag')} horizon=T+{best_by_dd.get('horizon')} "
        f"target={best_by_dd.get('target_pct')}% dd={best_by_dd.get('mean_drawdown')} net={best_by_dd.get('mean_net_return')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
