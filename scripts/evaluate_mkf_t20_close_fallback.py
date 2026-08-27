#!/usr/bin/env python3
"""Evaluate MKF lag0..7 target grid with T+20 close fallback for non-hits."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison import (
    build_mkf_post_cross_lag_t20_close_fallback_panel,
    build_t20_close_fallback_report,
    t20_close_fallback_summary_csv_rows,
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, default=None)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    return args


def _stock(task: tuple[str, dict[str, Any], str, str | None]) -> tuple[pd.DataFrame, dict[str, int]]:
    path_text, config, start_date, end_date = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    panel = build_mkf_post_cross_lag_t20_close_fallback_panel(path.stem, frame, config, start_date=start_date, end_date=end_date)
    return panel, {str(key): int(value) for key, value in panel.attrs.get("diagnostics", {}).items()}


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
    paths = sorted((path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)), key=lambda path: path.stem)
    if not paths:
        raise SystemExit("no current main-board Parquet files found")
    config = load_config(args.config)
    tasks = [(str(path), config, args.start_date, args.end_date) for path in paths]
    panels: list[pd.DataFrame] = []
    diagnostics: Counter[str] = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, (panel, stock_diagnostics) in enumerate(executor.map(_stock, tasks, chunksize=1), start=1):
            panels.append(panel)
            diagnostics.update(stock_diagnostics)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(paths)} codes", flush=True)
    code_list = [path.stem for path in paths]
    report = build_t20_close_fallback_report(
        panel=pd.concat(panels, ignore_index=True),
        diagnostics=dict(diagnostics),
        code_list=code_list,
        code_list_sha256=hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest(),
        start_date=args.start_date,
        end_date=args.end_date,
        workers=args.workers,
    )
    _atomic_json(args.output, report)
    if args.summary_csv is not None:
        _atomic_csv(args.summary_csv, t20_close_fallback_summary_csv_rows(report))


if __name__ == "__main__":
    main()
